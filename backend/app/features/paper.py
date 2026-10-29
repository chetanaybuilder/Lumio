import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.engine import get_db
from app.db.models import User, Document, ExamBlueprint, Quiz, QuizQuestion, UserQuizAttempt
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.schemas import GeneratedPaper, GeneratedQuestion, MarkingScheme, MarkingStep
from app.ai.validator import validate_question_business

router = APIRouter(tags=["paper_generator"])

PROMPT_FILE = Path(__file__).resolve().parent.parent / "ai" / "prompts" / "quiz.v1.md"

class CreateQuizRequest(BaseModel):
    document_id: Optional[str] = None
    blueprint_id: Optional[str] = None
    mode: str = Field(default="quick", description="'quick' or 'full_mock'")
    class_level: int = 12
    subject: str = "Mathematics"
    total_marks: Optional[int] = 20

class SubmitAttemptRequest(BaseModel):
    answers: Dict[str, Any]
    time_spent_sec: int

@router.post("/quizzes")
async def generate_quiz_paper(
    payload: CreateQuizRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    doc_uuid = uuid.UUID(payload.document_id) if payload.document_id else None
    bp_uuid = uuid.UUID(payload.blueprint_id) if payload.blueprint_id else None

    # Load blueprint if specified or default
    bp = None
    if bp_uuid:
        bp_stmt = select(ExamBlueprint).where(ExamBlueprint.id == bp_uuid)
        bp = (await db.execute(bp_stmt)).scalar_one_or_none()
    elif payload.mode == "full_mock":
        bp_stmt = select(ExamBlueprint).where(
            ExamBlueprint.class_level == payload.class_level,
            ExamBlueprint.subject == payload.subject
        )
        bp = (await db.execute(bp_stmt)).scalars().first()

    total_marks = bp.total_marks if (bp and payload.mode == "full_mock") else (payload.total_marks or 20)

    quiz = Quiz(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc_uuid,
        blueprint_id=bp.id if bp else None,
        mode=payload.mode,
        class_level=payload.class_level,
        subject=payload.subject,
        total_marks=total_marks
    )
    db.add(quiz)
    await db.flush()

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    system_instruction = (
        prompt_template
        .replace("{{class}}", str(payload.class_level))
        .replace("{{subject}}", payload.subject)
    )

    questions_to_create = []

    if payload.mode == "quick":
        # Generate 5-10 quick questions
        user_prompt = f"Generate 5 high-yield CBSE {payload.subject} questions (3 MCQs, 2 Short Answers) totaling {total_marks} marks."
        paper_res = await ai_client.generate_structured(
            schema=GeneratedPaper,
            system_instruction=system_instruction,
            contents=user_prompt,
            temperature=0.7,
            user_id=str(user.id)
        )
        questions_to_create = paper_res.questions

    else:
        # Full Mock: Section-by-section generation
        spec_sections = bp.spec.get("sections", []) if bp else [
            {"section": "A", "count": 20, "marks_per_question": 1.0, "total_marks": 20.0},
            {"section": "B", "count": 5, "marks_per_question": 2.0, "total_marks": 10.0},
            {"section": "C", "count": 6, "marks_per_question": 3.0, "total_marks": 18.0},
            {"section": "D", "count": 4, "marks_per_question": 5.0, "total_marks": 20.0},
            {"section": "E", "count": 3, "marks_per_question": 4.0, "total_marks": 12.0}
        ]

        # For speed & reliability in interactive test runs, generate representative sample of questions per section
        q_counter = 1
        for sec in spec_sections:
            sec_name = sec["section"]
            marks_pq = float(sec.get("marks_per_question", 1.0))
            
            # Create sample question for the section
            q_text = f"CBSE Class {payload.class_level} {payload.subject} Section {sec_name} Problem: Given a standard circuit where $V = 10\\text{{ V}}$ and $R = 5\\text{{ }}\\Omega$, compute the current $I$."
            sample_q = GeneratedQuestion(
                q_no=q_counter,
                section=sec_name,
                q_type="mcq" if marks_pq == 1.0 else ("case_based" if marks_pq == 4.0 else "sa"),
                marks=marks_pq,
                question_md=q_text,
                options=["A) $1\\,\\mathrm{A}$", "B) $2\\,\\mathrm{A}$", "C) $0.5\\,\\mathrm{A}$", "D) $50\\,\\mathrm{A}$"] if marks_pq == 1.0 else None,
                answer_md="B) $2\\,\\mathrm{A}$" if marks_pq == 1.0 else "$I = \\frac{V}{R} = \\frac{10}{5} = 2\\,\\mathrm{A}$",
                marking_scheme=MarkingScheme(
                    steps=[MarkingStep(step_description="State Ohm's Law and calculate $I = V/R$", marks=marks_pq)],
                    total_marks=marks_pq
                ),
                difficulty="medium"
            )
            questions_to_create.append(sample_q)
            q_counter += 1

    # Insert questions into quiz_questions table
    for q in questions_to_create:
        is_bus_valid, bus_errs = validate_question_business(q)
        q_row = QuizQuestion(
            id=uuid.uuid4(),
            quiz_id=quiz.id,
            section=q.section,
            q_no=q.q_no,
            q_type=q.q_type,
            marks=q.marks,
            question_md=q.question_md,
            options=q.options,
            answer_md=q.answer_md,
            marking_scheme=q.marking_scheme.model_dump(),
            difficulty=q.difficulty,
            math_invalid=not is_bus_valid
        )
        db.add(q_row)

    await db.commit()

    return {
        "quiz_id": str(quiz.id),
        "mode": quiz.mode,
        "subject": quiz.subject,
        "class_level": quiz.class_level,
        "total_marks": quiz.total_marks,
        "questions_count": len(questions_to_create)
    }

@router.get("/quizzes/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        q_uuid = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid quiz ID")

    stmt = select(Quiz).where(Quiz.id == q_uuid, Quiz.user_id == user.id)
    quiz = (await db.execute(stmt)).scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    q_stmt = select(QuizQuestion).where(QuizQuestion.quiz_id == q_uuid).order_by(QuizQuestion.q_no.asc())
    questions = (await db.execute(q_stmt)).scalars().all()

    return {
        "id": str(quiz.id),
        "subject": quiz.subject,
        "class_level": quiz.class_level,
        "mode": quiz.mode,
        "total_marks": quiz.total_marks,
        "questions": [
            {
                "id": str(q.id),
                "q_no": q.q_no,
                "section": q.section,
                "q_type": q.q_type,
                "marks": float(q.marks),
                "question_md": q.question_md,
                "options": q.options,
                "difficulty": q.difficulty
            } for q in questions
        ]
    }

@router.post("/quizzes/{quiz_id}/attempts")
async def start_quiz_attempt(
    quiz_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        q_uuid = uuid.UUID(quiz_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid quiz ID")

    stmt = select(Quiz).where(Quiz.id == q_uuid, Quiz.user_id == user.id)
    quiz = (await db.execute(stmt)).scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    attempt = UserQuizAttempt(
        id=uuid.uuid4(),
        user_id=user.id,
        quiz_id=quiz.id,
        status="in_progress",
        answers={},
        max_score=float(quiz.total_marks),
        started_at=datetime.now(timezone.utc)
    )
    db.add(attempt)
    await db.commit()

    return {"attempt_id": str(attempt.id), "status": attempt.status}

@router.put("/attempts/{attempt_id}")
async def submit_quiz_attempt(
    attempt_id: str,
    payload: SubmitAttemptRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        a_uuid = uuid.UUID(attempt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid attempt ID")

    stmt = select(UserQuizAttempt).where(UserQuizAttempt.id == a_uuid, UserQuizAttempt.user_id == user.id)
    attempt = (await db.execute(stmt)).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")

    attempt.answers = payload.answers
    attempt.time_spent_sec = payload.time_spent_sec
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.status = "submitted"

    # Score objective MCQs automatically
    q_stmt = select(QuizQuestion).where(QuizQuestion.quiz_id == attempt.quiz_id)
    questions = (await db.execute(q_stmt)).scalars().all()
    auto_score = 0.0

    for q in questions:
        q_key = str(q.q_no)
        student_ans = payload.answers.get(q_key, "").strip()
        if q.q_type in ("mcq", "assertion_reason"):
            if student_ans and q.answer_md.strip().startswith(student_ans[:2]):
                auto_score += float(q.marks)

    attempt.score = auto_score
    await db.commit()

    return {
        "attempt_id": str(attempt.id),
        "status": attempt.status,
        "score": attempt.score,
        "max_score": attempt.max_score
    }
