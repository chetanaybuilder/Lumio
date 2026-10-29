import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.db.engine import get_db
from app.db.models import User, StudyNote, Flashcard
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.schemas import FlashcardsList

router = APIRouter(tags=["flashcards"])

PROMPT_FILE = Path(__file__).resolve().parent.parent / "ai" / "prompts" / "flashcards.v1.md"

class ReviewCardRequest(BaseModel):
    quality: int = Field(ge=0, le=5, description="SM-2 recall quality from 0 (total blackout) to 5 (perfect recall)")

def calculate_sm2(
    quality: int,
    repetitions: int,
    interval_days: int,
    ease_factor: float
) -> tuple[int, int, float]:
    """
    SuperMemo-2 (SM-2) Spaced Repetition Algorithm.
    Returns: (new_repetitions, new_interval_days, new_ease_factor)
    """
    if quality < 3:
        new_repetitions = 0
        new_interval_days = 1
        new_ease = ease_factor  # Keep ease on failure or slightly lower
    else:
        if repetitions == 0:
            new_interval_days = 1
        elif repetitions == 1:
            new_interval_days = 6
        else:
            new_interval_days = max(1, round(interval_days * ease_factor))

        new_repetitions = repetitions + 1
        # Ease update formula: ease' = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        new_ease = max(1.3, ease_factor + delta)

    return new_repetitions, new_interval_days, new_ease

@router.post("/notes/{note_id}/flashcards")
async def generate_flashcards(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        n_uuid = uuid.UUID(note_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid note ID")

    stmt = select(StudyNote).where(StudyNote.id == n_uuid, StudyNote.user_id == user.id)
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Study note not found")

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    system_instruction = prompt_template.replace("{{class}}", "12").replace("{{subject}}", "CBSE")
    user_content = f"Generate 10 diverse high-yield flashcards from this note:\n\n{note.content_md[:4000]}"

    cards_result = await ai_client.generate_structured(
        schema=FlashcardsList,
        system_instruction=system_instruction,
        contents=user_content,
        temperature=0.3,
        user_id=str(user.id)
    )

    created_cards = []
    now = datetime.now(timezone.utc)

    for card in cards_result.cards:
        # Check if card with normalized front already exists for document
        norm_front = card.front.strip()
        chk_stmt = select(Flashcard).where(
            Flashcard.document_id == note.document_id,
            Flashcard.front == norm_front
        )
        existing = (await db.execute(chk_stmt)).scalar_one_or_none()
        if existing:
            continue

        f_card = Flashcard(
            id=uuid.uuid4(),
            user_id=user.id,
            document_id=note.document_id,
            note_id=note.id,
            front=norm_front,
            back=card.back.strip(),
            tags=card.tags or ["Revision"],
            ease_factor=2.5,
            interval_days=0,
            repetitions=0,
            due_at=now,
            suspended=False
        )
        db.add(f_card)
        created_cards.append(f_card)

    await db.commit()

    return {
        "note_id": str(note.id),
        "cards_created": len(created_cards),
        "total_generated": len(cards_result.cards)
    }

@router.get("/flashcards/due")
async def get_due_flashcards(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    stmt = select(Flashcard).where(
        Flashcard.user_id == user.id,
        Flashcard.due_at <= now,
        Flashcard.suspended.is_(False)
    ).order_by(Flashcard.due_at.asc()).limit(50)

    cards = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(c.id),
            "document_id": str(c.document_id),
            "front": c.front,
            "back": c.back,
            "tags": c.tags,
            "ease_factor": c.ease_factor,
            "interval_days": c.interval_days,
            "repetitions": c.repetitions,
            "due_at": c.due_at.isoformat()
        } for c in cards
    ]

@router.post("/flashcards/{card_id}/review")
async def review_flashcard(
    card_id: str,
    payload: ReviewCardRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        c_uuid = uuid.UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid card ID")

    stmt = select(Flashcard).where(Flashcard.id == c_uuid, Flashcard.user_id == user.id)
    card = (await db.execute(stmt)).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    new_rep, new_int, new_ease = calculate_sm2(
        quality=payload.quality,
        repetitions=card.repetitions,
        interval_days=card.interval_days,
        ease_factor=card.ease_factor
    )

    now = datetime.now(timezone.utc)
    card.repetitions = new_rep
    card.interval_days = new_int
    card.ease_factor = new_ease
    card.last_reviewed_at = now
    card.due_at = now + timedelta(days=new_int)

    await db.commit()

    return {
        "id": str(card.id),
        "quality": payload.quality,
        "repetitions": card.repetitions,
        "interval_days": card.interval_days,
        "ease_factor": card.ease_factor,
        "next_due": card.due_at.isoformat()
    }
