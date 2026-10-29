from __future__ import annotations
import uuid
from datetime import datetime, date
from typing import List, Optional, Any
from sqlalchemy import (
    String, Integer, SmallInteger, BigInteger, Boolean, Numeric, Float,
    DateTime, Date, ForeignKey, Text, UniqueConstraint, Index, CheckConstraint, JSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY, INET
from sqlalchemy.sql import func

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

# Cross-dialect JSONB type: JSONB on PostgreSQL, JSON on SQLite
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
ARRAY_TEXT_TYPE = JSON().with_variant(ARRAY(String), "postgresql")
VECTOR_768_TYPE = Vector(768) if Vector is not None else Text
INET_TYPE = String().with_variant(INET, "postgresql")

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    google_sub: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    class_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    board: Mapped[str] = mapped_column(String, default="CBSE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions: Mapped[List[AuthSession]] = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[List[Document]] = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    study_notes: Mapped[List[StudyNote]] = relationship("StudyNote", back_populates="user", cascade="all, delete-orphan")
    flashcards: Mapped[List[Flashcard]] = relationship("Flashcard", back_populates="user", cascade="all, delete-orphan")
    cheat_sheets: Mapped[List[CheatSheet]] = relationship("CheatSheet", back_populates="user", cascade="all, delete-orphan")
    quizzes: Mapped[List[Quiz]] = relationship("Quiz", back_populates="user", cascade="all, delete-orphan")
    user_mistakes: Mapped[List[UserMistake]] = relationship("UserMistake", back_populates="user", cascade="all, delete-orphan")
    tutor_sessions: Mapped[List[TutorSession]] = relationship("TutorSession", back_populates="user", cascade="all, delete-orphan")
    exam_targets: Mapped[List[ExamTarget]] = relationship("ExamTarget", back_populates="user", cascade="all, delete-orphan")

class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(INET_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("auth_sessions.id", ondelete="SET NULL"), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    class_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    r2_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    r2_upload_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ocr_page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="uploading", nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="documents")
    chunks: Mapped[List[DocumentChunk]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    jobs: Mapped[List[IngestionJob]] = relationship("IngestionJob", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "sha256", name="uq_user_sha256"),
    )

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String, default="ingest", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_completed_page: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_pct: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    locked_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="jobs")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[List[str]] = mapped_column(ARRAY_TEXT_TYPE, default=list, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    has_math: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    math_invalid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding = mapped_column(VECTOR_768_TYPE, nullable=True)

    document: Mapped[Document] = relationship("Document", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_doc_chunk_idx"),
    )

class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    class_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    chapter_no: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weightage_marks: Mapped[Optional[float]] = mapped_column(Numeric(4, 1), nullable=True)
    syllabus_year: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    embedding = mapped_column(VECTOR_768_TYPE, nullable=True)

class ExamBlueprint(Base):
    __tablename__ = "exam_blueprints"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    class_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    syllabus_year: Mapped[str] = mapped_column(String, nullable=False)
    total_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("class_level", "subject", "syllabus_year", name="uq_blueprint_spec"),
    )

class StudyNote(Base):
    __tablename__ = "study_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    math_invalid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="study_notes")

class CoverageReport(Base):
    __tablename__ = "coverage_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_notes.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    syllabus_year: Mapped[str] = mapped_column(String, nullable=False)
    total_topics: Mapped[int] = mapped_column(Integer, nullable=False)
    covered_topics: Mapped[int] = mapped_column(Integer, nullable=False)
    missing: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    note_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("study_notes.id", ondelete="SET NULL"), nullable=True)
    source_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY_TEXT_TYPE, default=list, nullable=False)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="flashcards")

    __table_args__ = (
        UniqueConstraint("document_id", "front", name="uq_doc_front"),
    )

class CheatSheet(Base):
    __tablename__ = "cheat_sheets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    formula_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    math_invalid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="cheat_sheets")

class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    blueprint_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("exam_blueprints.id", ondelete="SET NULL"), nullable=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    class_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    total_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="quizzes")
    questions: Mapped[List[QuizQuestion]] = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")
    attempts: Mapped[List[UserQuizAttempt]] = relationship("UserQuizAttempt", back_populates="quiz", cascade="all, delete-orphan")

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    section: Mapped[str] = mapped_column(String(1), nullable=False)
    q_no: Mapped[int] = mapped_column(Integer, nullable=False)
    q_type: Mapped[str] = mapped_column(String, nullable=False)
    marks: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    question_md: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list]] = mapped_column(JSON_TYPE, nullable=True)
    answer_md: Mapped[str] = mapped_column(Text, nullable=False)
    marking_scheme: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_chunk_ids: Mapped[list] = mapped_column(JSON_TYPE, default=list, nullable=False)
    math_invalid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="questions")

    __table_args__ = (
        UniqueConstraint("quiz_id", "q_no", name="uq_quiz_q_no"),
    )

class UserQuizAttempt(Base):
    __tablename__ = "user_quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="in_progress", nullable=False)
    answers: Mapped[dict] = mapped_column(JSON_TYPE, default=dict, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    max_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    time_spent_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    quiz: Mapped[Quiz] = relationship("Quiz", back_populates="attempts")
    evaluations: Mapped[List[AnswerEvaluation]] = relationship("AnswerEvaluation", back_populates="attempt", cascade="all, delete-orphan")

class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user_quiz_attempts.id", ondelete="CASCADE"), nullable=True)
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("quiz_questions.id", ondelete="SET NULL"), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    max_marks: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    awarded_marks: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    step_breakdown: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    feedback_md: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    attempt: Mapped[Optional[UserQuizAttempt]] = relationship("UserQuizAttempt", back_populates="evaluations")

class UserMistake(Base):
    __tablename__ = "user_mistakes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("quiz_questions.id", ondelete="SET NULL"), nullable=True)
    attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user_quiz_attempts.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    student_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_md: Mapped[str] = mapped_column(Text, nullable=False)
    times_missed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_missed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="user_mistakes")
    drills: Mapped[List[MistakeDrill]] = relationship("MistakeDrill", back_populates="mistake", cascade="all, delete-orphan")

class MistakeDrill(Base):
    __tablename__ = "mistake_drills"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    mistake_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_mistakes.id", ondelete="CASCADE"), nullable=False)
    questions: Mapped[list] = mapped_column(JSON_TYPE, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    mistake: Mapped[UserMistake] = relationship("UserMistake", back_populates="drills")

class TutorSession(Base):
    __tablename__ = "tutor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="tutor_sessions")
    messages: Mapped[List[TutorMessage]] = relationship("TutorMessage", back_populates="session", cascade="all, delete-orphan")

class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hint_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    session: Mapped[TutorSession] = relationship("TutorSession", back_populates="messages")

class ExamTarget(Base):
    __tablename__ = "exam_targets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    class_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User", back_populates="exam_targets")
    roadmap_items: Mapped[List[RoadmapItem]] = relationship("RoadmapItem", back_populates="exam_target", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "class_level", "subject", "exam_date", name="uq_target_user_date"),
    )

class RoadmapItem(Base):
    __tablename__ = "roadmap_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_target_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_targets.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    est_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    exam_target: Mapped[ExamTarget] = relationship("ExamTarget", back_populates="roadmap_items")

    __table_args__ = (
        UniqueConstraint("exam_target_id", "topic_id", "plan_date", "task_type", name="uq_roadmap_item"),
    )

class UsageLedger(Base):
    __tablename__ = "usage_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    feature: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
