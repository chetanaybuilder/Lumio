"""
Pydantic Schemas — Lumio Backend
=================================

Defines the request and response data models used by FastAPI for
automatic validation, serialization, and OpenAPI documentation.

Request models
--------------
- ``DocumentRequest``  : Base for any endpoint that operates on one document.
- ``QuizRequest``      : Extends ``DocumentRequest`` with quiz-specific options.
- ``ChatRequest``      : Extends ``DocumentRequest`` with the student's question.
- ``ExportRequest``    : Extends ``DocumentRequest`` with the export format.

Response / generation models
----------------------------
- ``NoteSection``      : One section of generated study notes.
- ``NotesOutput``      : Complete notes response (title + sections).
- ``QuizQuestion``     : One quiz question with answer, explanation, and source.
- ``QuizOutput``       : Complete quiz response (title + questions).
- ``Flashcard``        : One front/back flashcard with source pages.
- ``FlashcardsOutput`` : Complete flashcard deck (title + cards).
- ``ChatOutput``       : Answer from Ask Lumio with cited source pages.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class DocumentRequest(BaseModel):
    """Base request referencing a single document by ID."""
    document_id: str = Field(min_length=1, max_length=80)


class QuizRequest(DocumentRequest):
    """Quiz generation request with configurable question count and difficulty."""
    count: int = Field(default=8, ge=3, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class ChatRequest(DocumentRequest):
    """Ask Lumio request containing the student's question."""
    question: str = Field(min_length=2, max_length=2000)


class ExportRequest(DocumentRequest):
    """PDF export request specifying which material type to export."""
    kind: Literal["deep-notes", "quick-notes", "quiz", "flashcards"]


# ---------------------------------------------------------------------------
# Study material output schemas (validated against Gemini responses)
# ---------------------------------------------------------------------------

class NoteSection(BaseModel):
    """One section of generated study notes with heading, content, and sources."""
    heading: str
    content: str
    source_pages: list[int] = Field(default_factory=list)


class SubtopicNote(BaseModel):
    """Detailed, structured notes for a single atomic subtopic."""
    subtopic_id: str
    chapter: str
    topic: str
    subtopic: str
    source_pages: list[int] = Field(default_factory=list)
    definition: str = ""
    explanation: str = ""
    formulas: list[str] = Field(default_factory=list)
    worked_example: str = ""
    comparison_table: str = ""
    common_mistakes: list[str] = Field(default_factory=list)
    exam_tips: list[str] = Field(default_factory=list)
    figures: list[dict] = Field(default_factory=list)


class DeepNotesOutput(BaseModel):
    """Elite Deep Notes with granular subtopic breakdown and table of contents."""
    title: str
    subtopics: list[SubtopicNote] = Field(default_factory=list)
    sections: list[NoteSection] = Field(default_factory=list)


class TopicQuickNote(BaseModel):
    """High-yield one-screen revision summary for a topic."""
    topic_id: str
    chapter: str
    topic: str
    source_pages: list[int] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    key_formulas: list[str] = Field(default_factory=list)
    memory_trick: str = ""


class QuickNotesOutput(BaseModel):
    """Concise rapid revision deck structured per topic."""
    title: str
    topics: list[TopicQuickNote] = Field(default_factory=list)
    sections: list[NoteSection] = Field(default_factory=list)


class NotesOutput(BaseModel):
    """Complete notes response containing title, sections, and optional rich subtopics."""
    title: str
    sections: list[NoteSection]
    subtopics: list[SubtopicNote] = Field(default_factory=list)
    topics: list[TopicQuickNote] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    """A single quiz question with its answer, explanation, and metadata."""
    type: Literal["multiple_choice", "true_false", "short_answer"]
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    source_pages: list[int] = Field(default_factory=list)


class QuizOutput(BaseModel):
    """Complete quiz with a title and a list of validated questions."""
    title: str
    questions: list[QuizQuestion]


class Flashcard(BaseModel):
    """A single flashcard with a question (front) and answer (back)."""
    front: str
    back: str
    source_pages: list[int] = Field(default_factory=list)


class FlashcardsOutput(BaseModel):
    """Complete flashcard deck with a title and a list of cards."""
    title: str
    cards: list[Flashcard]


class ChatOutput(BaseModel):
    """Ask Lumio response containing an answer and cited source pages."""
    answer: str
    source_pages: list[int] = Field(default_factory=list)


# These schemas validate every generated study artifact at the API boundary.