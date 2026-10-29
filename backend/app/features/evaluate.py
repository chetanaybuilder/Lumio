import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.engine import get_db
from app.db.models import User, QuizQuestion, AnswerEvaluation, UserMistake
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.schemas import EvaluationResult
from app.ai.validator import validate_evaluation_business

router = APIRouter(tags=["marks_improvement"])

PROMPT_FILE = Path(__file__).resolve().parent.parent / "ai" / "prompts" / "evaluate.v1.md"

class EvaluateAnswerRequest(BaseModel):
    question_id: str
    attempt_id: Optional[str] = None
    student_answer: str

@router.post("/evaluate")
async def evaluate_answer(
    payload: EvaluateAnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        q_uuid = uuid.UUID(payload.question_id)
        a_uuid = uuid.UUID(payload.attempt_id) if payload.attempt_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid question or attempt ID")

    stmt = select(QuizQuestion).where(QuizQuestion.id == q_uuid)
    question = (await db.execute(stmt)).scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    system_instruction = prompt_template.replace("{{class}}", "12").replace("{{subject}}", "CBSE")

    user_prompt = (
        f"QUESTION:\n{question.question_md}\n\n"
        f"MAX MARKS: {question.marks}\n\n"
        f"OFFICIAL MARKING SCHEME:\n{json.dumps(question.marking_scheme, indent=2)}\n\n"
        f"STUDENT ANSWER:\n{payload.student_answer.strip()}"
    )

    eval_result = await ai_client.generate_structured(
        schema=EvaluationResult,
        system_instruction=system_instruction,
        contents=user_prompt,
        temperature=0.1,
        user_id=str(user.id)
    )

    # Validate business rules
    is_valid, bus_errors = validate_evaluation_business(eval_result)

    now = datetime.now(timezone.utc)
    evaluation_record = AnswerEvaluation(
        id=uuid.uuid4(),
        user_id=user.id,
        attempt_id=a_uuid,
        question_id=question.id,
        question_text=question.question_md,
        answer_text=payload.student_answer,
        max_marks=eval_result.max_total,
        awarded_marks=eval_result.awarded_total,
        step_breakdown=[s.model_dump() for s in eval_result.steps],
        feedback_md=eval_result.feedback_md,
        model=ai_client.model_name,
        created_at=now
    )
    db.add(evaluation_record)

    # If student lost marks, log or update user_mistakes table
    if eval_result.awarded_total < eval_result.max_total:
        cat = eval_result.identified_mistake_category or "concept_gap"
        # Check if mistake already exists for user and question
        mistake_stmt = select(UserMistake).where(
            UserMistake.user_id == user.id,
            UserMistake.question_id == question.id
        )
        existing_mistake = (await db.execute(mistake_stmt)).scalar_one_or_none()
        if existing_mistake:
            existing_mistake.times_missed += 1
            existing_mistake.last_missed_at = now
            existing_mistake.student_answer = payload.student_answer
            existing_mistake.resolved = False
        else:
            mistake = UserMistake(
                id=uuid.uuid4(),
                user_id=user.id,
                question_id=question.id,
                attempt_id=a_uuid,
                topic_id=question.topic_id,
                category=cat,
                student_answer=payload.student_answer,
                correct_answer=question.answer_md,
                explanation_md=eval_result.feedback_md,
                times_missed=1,
                resolved=False,
                last_missed_at=now,
                created_at=now
            )
            db.add(mistake)

    await db.commit()

    return {
        "evaluation_id": str(evaluation_record.id),
        "awarded_marks": float(eval_result.awarded_total),
        "max_marks": float(eval_result.max_total),
        "percentage": round((eval_result.awarded_total / max(0.1, eval_result.max_total)) * 100, 1),
        "steps": [s.model_dump() for s in eval_result.steps],
        "feedback_md": eval_result.feedback_md,
        "model_answer_md": eval_result.model_answer_md,
        "how_to_gain_marks": eval_result.how_to_gain_marks,
        "mistake_category": eval_result.identified_mistake_category
    }
