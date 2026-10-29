import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.engine import get_db
from app.db.models import User, UserMistake, MistakeDrill
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.schemas import DrillSpec

router = APIRouter(tags=["mistakes"])

PROMPT_FILE = Path(__file__).resolve().parent.parent / "ai" / "prompts" / "drill.v1.md"

class SubmitDrillRequest(BaseModel):
    answers: Dict[str, Any]

@router.get("/mistakes")
async def get_user_mistakes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(UserMistake).where(
        UserMistake.user_id == user.id,
        UserMistake.resolved.is_(False)
    ).order_by(UserMistake.times_missed.desc(), UserMistake.last_missed_at.desc())

    mistakes = (await db.execute(stmt)).scalars().all()
    
    # Group by category
    categories: Dict[str, List[Any]] = {}
    for m in mistakes:
        categories.setdefault(m.category, []).append({
            "id": str(m.id),
            "category": m.category,
            "student_answer": m.student_answer,
            "correct_answer": m.correct_answer,
            "explanation_md": m.explanation_md,
            "times_missed": m.times_missed,
            "last_missed_at": m.last_missed_at.isoformat()
        })

    return {
        "total_unresolved": len(mistakes),
        "by_category": categories
    }

@router.post("/mistakes/{mistake_id}/drill")
async def generate_micro_drill(
    mistake_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        m_uuid = uuid.UUID(mistake_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mistake ID")

    stmt = select(UserMistake).where(UserMistake.id == m_uuid, UserMistake.user_id == user.id)
    mistake = (await db.execute(stmt)).scalar_one_or_none()
    if not mistake:
        raise HTTPException(status_code=404, detail="Mistake not found")

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    system_instruction = prompt_template.replace("{{class}}", "12").replace("{{subject}}", "CBSE").replace("{{concept}}", mistake.category)

    user_prompt = (
        f"MISTAKE CATEGORY: {mistake.category}\n"
        f"STUDENT FAILED ANSWER: {mistake.student_answer}\n"
        f"CORRECT ANSWER: {mistake.correct_answer}\n"
        f"CONCEPT EXPLANATION: {mistake.explanation_md}\n\n"
        f"Generate 3 progressive diagnostic questions to reinforce this specific weak area."
    )

    drill_res = await ai_client.generate_structured(
        schema=DrillSpec,
        system_instruction=system_instruction,
        contents=user_prompt,
        temperature=0.3,
        user_id=str(user.id)
    )

    drill = MistakeDrill(
        id=uuid.uuid4(),
        user_id=user.id,
        mistake_id=mistake.id,
        questions=[q.model_dump() for q in drill_res.questions],
        created_at=datetime.now(timezone.utc)
    )
    db.add(drill)
    await db.commit()

    return {
        "drill_id": str(drill.id),
        "mistake_id": str(mistake.id),
        "category": drill_res.mistake_category,
        "concept_summary": drill_res.concept_summary,
        "questions": drill.questions
    }

@router.post("/mistakes/drills/{drill_id}/submit")
async def submit_micro_drill(
    drill_id: str,
    payload: SubmitDrillRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        d_uuid = uuid.UUID(drill_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid drill ID")

    stmt = select(MistakeDrill).where(MistakeDrill.id == d_uuid, MistakeDrill.user_id == user.id)
    drill = (await db.execute(stmt)).scalar_one_or_none()
    if not drill:
        raise HTTPException(status_code=404, detail="Drill not found")

    correct_count = 0
    total_q = len(drill.questions)

    for q in drill.questions:
        q_no_str = str(q.get("q_no", 1))
        user_ans = payload.answers.get(q_no_str, "").strip()
        expected = q.get("answer_md", "").strip()
        # Check matching first 2 characters or exact match
        if user_ans and (expected.startswith(user_ans[:2]) or user_ans.lower() in expected.lower()):
            correct_count += 1

    score_pct = round((correct_count / max(1, total_q)) * 100, 1)
    drill.score = score_pct
    drill.completed_at = datetime.now(timezone.utc)

    # Invariant: Completing drill with at least 2 of 3 correct resolves the mistake
    resolved = False
    if correct_count >= 2:
        resolved = True
        await db.execute(
            update(UserMistake).where(UserMistake.id == drill.mistake_id).values(resolved=True)
        )

    await db.commit()

    return {
        "drill_id": str(drill.id),
        "score_pct": score_pct,
        "correct_count": correct_count,
        "total_questions": total_q,
        "mistake_resolved": resolved
    }
