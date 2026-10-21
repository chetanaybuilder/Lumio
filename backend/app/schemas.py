from typing import Literal

from pydantic import BaseModel, Field


class DocumentRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=80)


class QuizRequest(DocumentRequest):
    count: int = Field(default=8, ge=3, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class ChatRequest(DocumentRequest):
    question: str = Field(min_length=2, max_length=2000)


class ExportRequest(DocumentRequest):
    kind: Literal["deep-notes", "quick-notes", "quiz", "flashcards"]


class NoteSection(BaseModel):
    heading: str
    content: str
    source_pages: list[int] = Field(default_factory=list)


class NotesOutput(BaseModel):
    title: str
    sections: list[NoteSection]


class QuizQuestion(BaseModel):
    type: Literal["multiple_choice", "true_false", "short_answer"]
    question: str
    options: list[str] = Field(default_factory=list)
    answer: str
    explanation: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    source_pages: list[int] = Field(default_factory=list)


class QuizOutput(BaseModel):
    title: str
    questions: list[QuizQuestion]


class Flashcard(BaseModel):
    front: str
    back: str
    source_pages: list[int] = Field(default_factory=list)


class FlashcardsOutput(BaseModel):
    title: str
    cards: list[Flashcard]


class ChatOutput(BaseModel):
    answer: str
    source_pages: list[int] = Field(default_factory=list)


# These schemas validate every generated study artifact at the API boundary.