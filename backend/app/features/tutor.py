import json
import uuid
from pathlib import Path
from typing import Optional, AsyncGenerator
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.engine import get_db
from app.db.models import User, Document, TutorSession, TutorMessage, UserQuizAttempt
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.retrieval import retrieve_document_chunks

router = APIRouter(tags=["cbse_tutor"])

PROMPT_FILE = Path(__file__).resolve().parent.parent / "ai" / "prompts" / "tutor.v1.md"

class CreateSessionRequest(BaseModel):
    document_id: Optional[str] = None
    topic_id: Optional[str] = None
    title: Optional[str] = "CBSE Socratic Tutoring"

class SendMessageRequest(BaseModel):
    content: str
    current_hint_level: Optional[int] = 0

@router.post("/tutor/sessions")
async def create_tutor_session(
    payload: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    doc_uuid = uuid.UUID(payload.document_id) if payload.document_id else None
    topic_uuid = uuid.UUID(payload.topic_id) if payload.topic_id else None

    session = TutorSession(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc_uuid,
        topic_id=topic_uuid,
        title=payload.title or "CBSE Study Session"
    )
    db.add(session)
    await db.commit()

    return {"session_id": str(session.id), "title": session.title}

@router.post("/tutor/sessions/{session_id}/messages")
async def send_tutor_message(
    session_id: str,
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        s_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    stmt = select(TutorSession).where(TutorSession.id == s_uuid, TutorSession.user_id == user.id)
    res = await db.execute(stmt)
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Tutor session not found")

    # Safety Invariant: Check if user has an active quiz in progress
    active_quiz_stmt = select(UserQuizAttempt).where(
        UserQuizAttempt.user_id == user.id,
        UserQuizAttempt.status == "in_progress"
    )
    active_attempt = (await db.execute(active_quiz_stmt)).scalars().first()
    
    # Save student message
    user_msg = TutorMessage(
        id=uuid.uuid4(),
        session_id=sess.id,
        role="user",
        content=payload.content.strip(),
        hint_level=payload.current_hint_level or 0
    )
    db.add(user_msg)
    await db.commit()

    # If exam is in progress and message looks like asking for exam answer, refuse
    if active_attempt and any(k in payload.content.lower() for k in ("solve", "answer", "question", "quiz", "exam")):
        refusal_text = "I notice you currently have a CBSE test in progress! To preserve examination integrity, I cannot provide answers during an active exam. Please submit your exam attempt first, and we can review every question together afterwards."
        bot_msg = TutorMessage(
            id=uuid.uuid4(),
            session_id=sess.id,
            role="assistant",
            content=refusal_text,
            hint_level=0
        )
        db.add(bot_msg)
        await db.commit()

        async def _refusal_sse():
            yield f"data: {json.dumps({'token': refusal_text})}\n\n"
            yield f"data: {json.dumps({'done': True, 'hint_level': 0})}\n\n"
        return StreamingResponse(_refusal_sse(), media_type="text/event-stream")

    # Retrieve context chunks if document is attached
    context_chunks = []
    if sess.document_id:
        context_chunks = await retrieve_document_chunks(db, sess.document_id, user.id, payload.content, top_k=6)
    
    context_str = "\n\n".join([f"[{c.heading_path}]: {c.content}" for c in context_chunks])

    # Fetch last 10 messages for dialogue memory
    history_stmt = select(TutorMessage).where(TutorMessage.session_id == sess.id).order_by(TutorMessage.created_at.desc()).limit(10)
    history_rows = (await db.execute(history_stmt)).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]

    # Compute next hint level
    cur_lvl = payload.current_hint_level or 0
    # Advance hint level if student expresses struggle or asks for hint
    struggle_signals = ["stuck", "don't know", "dont know", "hint", "help", "wrong", "next step", "solution", "how"]
    if any(s in payload.content.lower() for s in struggle_signals):
        next_hint_level = min(4, cur_lvl + 1)
    else:
        next_hint_level = cur_lvl

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    system_instruction = (
        prompt_template
        .replace("{{class}}", "12")
        .replace("{{subject}}", "CBSE Science")
        .replace("{{hint_level}}", str(next_hint_level))
        + f"\n\nGROUNDING TEXTBOOK CHUNKS:\n{context_str}"
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        accumulated_tokens = []
        try:
            async for token in ai_client.stream_chat(
                system_instruction=system_instruction,
                history=history,
                user_message=payload.content,
                temperature=0.5,
                user_id=str(user.id)
            ):
                accumulated_tokens.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"

            full_reply = "".join(accumulated_tokens)
            
            # Save assistant reply to database
            async with get_db() as save_db:
                reply_record = TutorMessage(
                    id=uuid.uuid4(),
                    session_id=sess.id,
                    role="assistant",
                    content=full_reply,
                    hint_level=next_hint_level
                )
                save_db.add(reply_record)
                await save_db.commit()

            yield f"data: {json.dumps({'done': True, 'hint_level': next_hint_level})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
