"""
Main Application — Lumio Backend
==================================

The FastAPI application entry point.  This module wires together every
subsystem — PDF extraction (with OCR), text preprocessing, structure
detection, chunking, embedding, vector storage, study-material
generation, chat, and PDF export — behind a session-authenticated REST
API.

Lifecycle
---------
On startup the Chroma collection is cleared (orphaned vectors from a
previous process are unreachable).  A background task runs every 60 s to
clean up expired sessions and their vector data.  On shutdown the
cleanup task is gracefully cancelled.

Concurrency
-----------
A semaphore (``generation_slots``) limits the number of concurrent Groq
generation calls to 4 to avoid overwhelming the provider's free-tier
rate limits.

Session security
----------------
Every document operation requires a valid ``X-Session-Token`` header.
Document ownership is checked before reads, writes, and deletes, so one
session cannot access another session's data.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from tempfile import NamedTemporaryFile
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.chunker import create_chunks
from app.config import FRONTEND_ORIGINS, MAX_UPLOAD_BYTES, SESSION_TTL_SECONDS, TEMP_DIR
from app.embedding_generator import generate_embeddings, generate_embedding
from app.export_service import make_pdf
from app.groq_client import generate_structured
from app.pdf_extractor import (
    PDFCorruptedError,
    PDFEncryptedError,
    PDFPageLimitError,
    PDFScannedError,
    extract_text_from_pdf,
)
from app.prompt_templates import chat_prompt, study_prompt
from app.schemas import (
    ChatOutput,
    ChatRequest,
    DeepNotesOutput,
    DocumentRequest,
    ExportRequest,
    FlashcardsOutput,
    NoteSection,
    NotesOutput,
    QuickNotesOutput,
    QuizOutput,
    QuizRequest,
    SubtopicNote,
    TopicQuickNote,
)
from app.session_manager import (
    StudySession,
    create_session,
    expired_sessions,
    get_session,
    remove_session,
)
from app.structure_detector import build_hierarchical_outline, detect_structure
from app.text_preprocessor import clean_pages
from app.vector_store import clear_all_chunks, delete_document, query_chunks, store_chunks


# ---------------------------------------------------------------------------
# Logging and concurrency controls
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lumio")

# Limit concurrent Gemini generation calls to avoid rate-limit errors.
generation_slots = asyncio.Semaphore(2)


# ---------------------------------------------------------------------------
# Background session cleanup
# ---------------------------------------------------------------------------

async def cleanup_expired_sessions() -> None:
    """
    Find all expired sessions, delete their vector data, and remove them.

    If vector cleanup fails for any document the session is kept so that
    the next cleanup cycle can retry.
    """
    for session in await expired_sessions():
        cleaned = True
        for document_id in session.documents:
            try:
                await run_in_threadpool(delete_document, document_id, session.token)
            except Exception:
                cleaned = False
                logger.exception("Expired session vector cleanup failed")
        if cleaned:
            await remove_session(session.token)


async def cleanup_loop() -> None:
    """Run ``cleanup_expired_sessions`` every 60 seconds until cancelled."""
    while True:
        await asyncio.sleep(60)
        await cleanup_expired_sessions()


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    FastAPI lifespan context manager.

    - **Startup**: clears orphaned Chroma vectors and starts the session
      cleanup background task.
    - **Shutdown**: cancels the cleanup task gracefully.
    """
    try:
        clear_all_chunks()
    except Exception:
        logger.exception("Unable to clean vectors left by the previous process")
        raise
    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task


# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------

app = FastAPI(title="Lumio API", version="1.0.0", lifespan=lifespan)

# CORS middleware — only the configured frontend origins are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Session-Token"],
)


# ---------------------------------------------------------------------------
# Dependency injection helpers
# ---------------------------------------------------------------------------

async def require_session(x_session_token: str | None = Header(default=None)) -> StudySession:
    """
    FastAPI dependency that extracts and validates the session token.

    Raises ``401`` if the token is missing or the session has expired.
    """
    session = await get_session(x_session_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Study session is missing or expired.")
    return session


def owned_document(session: StudySession, document_id: str) -> dict:
    """
    Return the document record if it belongs to *session*, else raise ``404``.
    """
    document = session.documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found in this study session.")
    return document


# ---------------------------------------------------------------------------
# Source-page validation helper
# ---------------------------------------------------------------------------

def valid_pages(material: dict, allowed_pages: set[int]) -> dict:
    """
    Strip any generated source-page references not present in *allowed_pages*.

    This prevents the AI model from hallucinating page numbers that do
    not exist in the uploaded document.
    """
    def filter_pages(record: dict) -> None:
        record["source_pages"] = [page for page in record.get("source_pages", []) if page in allowed_pages]

    for section in material.get("sections", []):
        filter_pages(section)
    for item in material.get("questions", material.get("cards", [])):
        filter_pages(item)
    return material


def document_context(document: dict) -> tuple[str, set[int]]:
    """
    Build a representative, structured text context string across the entire
    document for comprehensive study material generation.

    Prioritizes chunks with diagrams and tables, while ensuring coverage
    across all detected sections from the beginning, middle, and end of the document.
    """
    chunks = document.get("chunks", [])
    if not chunks:
        return "", set()

    max_chars = 9000
    chosen_chunks = []

    if len(chunks) <= 8:
        chosen_chunks = list(chunks)
    else:
        visual_chunks = [c for c in chunks if c.get("has_diagram") or c.get("has_table")]
        step = max(1, len(chunks) // 10)
        sampled = [chunks[i] for i in range(0, len(chunks), step)]

        seen_texts = set()
        for c in visual_chunks + sampled:
            if c["text"] not in seen_texts:
                chosen_chunks.append(c)
                seen_texts.add(c["text"])

        chunk_order = {c["text"]: i for i, c in enumerate(chunks)}
        chosen_chunks.sort(key=lambda c: chunk_order.get(c["text"], 0))

    excerpts = []
    pages: set[int] = set()
    total_len = 0

    for chunk in chosen_chunks:
        chunk_pages = chunk.get("source_pages", [])
        excerpt = f"[Pages {', '.join(map(str, chunk_pages))}; {chunk.get('section', 'Section')}] {chunk['text']}"
        if total_len + len(excerpt) > max_chars:
            if not excerpts:
                excerpts.append(excerpt[:max_chars])
                pages.update(chunk_pages)
            break
        excerpts.append(excerpt)
        pages.update(chunk_pages)
        total_len += len(excerpt)

    return "\n\n".join(excerpts), pages




# ═══════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check() -> dict:
    """Return a simple health status for uptime monitoring."""
    return {"status": "healthy", "app": "Lumio"}


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@app.post("/api/sessions", status_code=201)
async def start_session() -> dict:
    """Create a new anonymous study session and return its token."""
    session = await create_session()
    return {"session_token": session.token, "expires_in": SESSION_TTL_SECONDS}


@app.delete("/api/sessions/current", status_code=204)
async def end_session(session: StudySession = Depends(require_session)) -> Response:
    """
    Explicitly close a study session.

    All document vectors are deleted from ChromaDB before the session
    record is removed from the in-memory registry.
    """
    for document_id in session.documents:
        try:
            delete_document(document_id, session.token)
        except Exception as error:
            logger.exception("Session vector cleanup failed")
            raise HTTPException(
                status_code=503,
                detail="Session cleanup failed; retry before closing this session.",
            ) from error
    await remove_session(session.token)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Document upload and management
# ---------------------------------------------------------------------------

@app.post("/api/documents/upload", status_code=201)
async def upload_pdf(file: UploadFile = File(...), session: StudySession = Depends(require_session)) -> dict:
    """
    Upload a PDF textbook for processing.

    Pipeline: receive file → validate → extract text (with OCR fallback)
    → clean → detect structure → chunk → embed → store vectors.

    The temporary upload file is always removed in the ``finally`` block.
    """
    # --- Guard: enforce per-session document limit ---
    if len(session.documents) >= 5:
        raise HTTPException(status_code=429, detail="A study session can contain up to five documents.")

    # --- Guard: require a .pdf filename ---
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = None
    document_id = uuid4().hex
    total_size = 0

    try:
        # --- Stream the upload to a temporary file with size enforcement ---
        with NamedTemporaryFile(mode="wb", suffix=".pdf", dir=TEMP_DIR, delete=False) as temp_file:
            temp_path = temp_file.name
            while content := await file.read(1024 * 1024):
                total_size += len(content)
                if total_size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="PDF exceeds the configured upload limit.")
                temp_file.write(content)

        # --- Validate the PDF magic bytes ---
        with open(temp_path, "rb") as saved_file:
            if b"%PDF-" not in saved_file.read(1024):
                raise HTTPException(status_code=400, detail="The uploaded file is not a readable PDF.")

        # --- Extract text from every page (with OCR fallback) ---
        pages = await run_in_threadpool(extract_text_from_pdf, temp_path)

        # --- Clean and normalize extracted text ---
        cleaned_pages = clean_pages(pages)
        if not any(page["text"] for page in cleaned_pages):
            raise HTTPException(status_code=422, detail="No readable text found. This PDF may require OCR or contains only images that could not be processed.")

        # --- Detect section structure and create overlapping chunks ---
        sections = detect_structure(cleaned_pages)
        chunks = create_chunks(sections)
        if not chunks:
            raise HTTPException(status_code=422, detail="No readable content or structure could be extracted from this PDF.")
        if len(chunks) > 1000:
            # Dynamically consolidate chunks for larger textbooks so they can be processed seamlessly
            chunks = create_chunks(sections, chunk_size=1000, overlap=100)
        if len(chunks) > 2000:
            chunks = chunks[:2000]

        # --- Generate embeddings for all chunks ---
        embeddings = await run_in_threadpool(generate_embeddings, [chunk["text"] for chunk in chunks])

        # --- Store chunks and embeddings in ChromaDB ---
        try:
            await run_in_threadpool(store_chunks, document_id, chunks, embeddings, session.token)
        except Exception:
            # Roll back partial writes if storage fails.
            try:
                await run_in_threadpool(delete_document, document_id, session.token)
            except Exception:
                logger.exception("Failed to roll back partial document vectors")
            raise

        # --- Register the document in the session ---
        document = {
            "filename": file.filename[:255],
            "page_count": len(pages),
            "sections": sections,
            "chunks": chunks,
            "materials": {},
        }
        session.documents[document_id] = document

        return {
            "document_id": document_id,
            "filename": document["filename"],
            "page_count": len(pages),
            "sections_detected": len(sections),
            "chunks_created": len(chunks),
            "status": "ready",
        }

    except HTTPException:
        raise
    except PDFPageLimitError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except PDFEncryptedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PDFScannedError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except PDFCorruptedError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Unable to read this PDF. Check that the file is not damaged.") from error
    except RuntimeError as error:
        logger.warning("Document processing could not complete: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="Document processing is temporarily unavailable. Check service configuration and retry.") from error
    except Exception as error:
        logger.exception("Document processing failed")
        raise HTTPException(status_code=502, detail="Document processing failed. Check service configuration and retry.") from error
    finally:
        # Always close the upload stream and remove the temporary file.
        await file.close()
        if temp_path:
            try:
                import os
                os.unlink(temp_path)
            except OSError:
                logger.warning("Temporary upload cleanup failed")


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str, session: StudySession = Depends(require_session)) -> dict:
    """Return metadata for an uploaded document owned by the current session."""
    document = owned_document(session, document_id)
    return {
        "document_id": document_id,
        "filename": document["filename"],
        "page_count": document["page_count"],
        "sections_detected": len(document["sections"]),
        "chunks_created": len(document["chunks"]),
    }


@app.delete("/api/documents/{document_id}", status_code=204)
async def delete_owned_document(document_id: str, session: StudySession = Depends(require_session)) -> Response:
    """Delete a document and its vectors from the current session."""
    owned_document(session, document_id)
    try:
        await run_in_threadpool(delete_document, document_id, session.token)
    except Exception as error:
        logger.exception("Document vector cleanup failed")
        raise HTTPException(
            status_code=503,
            detail="Document cleanup failed; retry before ending this session.",
        ) from error
    session.documents.pop(document_id, None)
    session.chat.pop(document_id, None)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Study material generation
# ---------------------------------------------------------------------------

async def generate_notes(request: DocumentRequest, session: StudySession, kind: str, instructions: str) -> dict:
    """
    Shared handler for deep-notes and quick-notes generation.

    Assembles a document context, prompts LLM for structured notes,
    validates source-page claims, enriches with outline subtopics/topics,
    and caches the result on the session.
    """
    document = owned_document(session, request.document_id)
    context, pages = document_context(document)
    sections = document.get("sections", [])
    outline = build_hierarchical_outline(sections)
    try:
        async with generation_slots:
            result = await run_in_threadpool(
                generate_structured,
                study_prompt(kind, document["filename"], context, instructions),
                NotesOutput,
            )
        material = valid_pages(result.model_dump(), pages)

        # If subtopics exist in outline and kind is deep-notes, ensure all subtopics are populated
        if kind == "deep-notes" and outline:
            if not material.get("subtopics"):
                subtopics_list = []
                for s in outline:
                    subtopics_list.append({
                        "subtopic_id": s["id"],
                        "chapter": s["chapter"],
                        "topic": s["topic"],
                        "subtopic": s["subtopic"],
                        "source_pages": [p for p in s.get("source_pages", [1]) if p in pages] or [1],
                        "definition": f"Core principles and definitions for {s['subtopic']}.",
                        "explanation": s.get("content", ""),
                        "formulas": [],
                        "worked_example": "",
                        "comparison_table": "",
                        "common_mistakes": [],
                        "exam_tips": [],
                        "figures": [],
                    })
                material["subtopics"] = subtopics_list

        # If topics exist in outline and kind is quick-notes, ensure topics are populated
        if kind == "quick-notes" and outline:
            if not material.get("topics"):
                from collections import defaultdict
                by_topic = defaultdict(list)
                for s in outline:
                    by_topic[(s["chapter"], s["topic"])].append(s)
                topics_list = []
                for idx, ((ch, top), subs) in enumerate(by_topic.items(), start=1):
                    t_pages = set()
                    for sub in subs:
                        t_pages.update(sub.get("source_pages", [1]))
                    topics_list.append({
                        "topic_id": f"topic_{idx}",
                        "chapter": ch,
                        "topic": top,
                        "source_pages": sorted([p for p in t_pages if p in pages]) or [1],
                        "bullets": [s["subtopic"] for s in subs][:8],
                        "key_formulas": [],
                        "memory_trick": "",
                    })
                material["topics"] = topics_list

        document["materials"][kind] = material
        return material
    except Exception as error:
        logger.exception("Study material generation failed")
        raise HTTPException(
            status_code=503,
            detail="Study material generation is temporarily unavailable. Please retry in a moment.",
        ) from error


@app.post("/api/study/deep-notes")
async def deep_notes(request: DocumentRequest, session: StudySession = Depends(require_session)) -> dict:
    """Generate detailed, section-by-section study notes from the textbook."""
    return await generate_notes(
        request, session, "deep-notes",
        "Generate comprehensive, structured notes across all chapters and sections. Include: Chapter/Section Overviews, Core Definitions, Visual & Diagram Mechanisms (explaining any figures, charts, or structural diagrams in depth), Mathematical Formulas & Scientific Units, Step-by-Step Processes, Worked Examples, Common Misconceptions, and Exam Takeaways.",
    )


@app.post("/api/study/quick-notes")
async def quick_notes(request: DocumentRequest, session: StudySession = Depends(require_session)) -> dict:
    """Generate concise revision notes with only essential information."""
    return await generate_notes(
        request, session, "quick-notes",
        "Generate a high-yield rapid revision sheet. Include: Key Formulas with parameter definitions, Essential Definitions, High-Frequency Exam Facts, Crucial Scientific Distinctions, and Memory Mnemonics.",
    )


@app.post("/api/study/quiz")
async def create_quiz(request: QuizRequest, session: StudySession = Depends(require_session)) -> dict:
    """
    Generate a quiz with the requested number of questions and difficulty.

    Validates that the response contains the correct question count,
    valid multiple-choice answers, and correct true/false formats.
    """
    document = owned_document(session, request.document_id)
    context, pages = document_context(document)
    prompt = study_prompt(
        "a quiz", document["filename"], context,
        f"Generate exactly {request.count} questions at {request.difficulty} difficulty. "
        f"Mix multiple_choice, true_false, and short_answer question types. "
        f"Include answer, explanation, and source pages.",
    )
    try:
        async with generation_slots:
            result = await run_in_threadpool(generate_structured, prompt, QuizOutput)

        # --- Validate question count ---
        if len(result.questions) != request.count:
            raise ValueError("Incorrect quiz question count")

        # --- Validate answer integrity for each question ---
        for item in result.questions:
            if item.type == "multiple_choice" and (len(item.options) < 2 or item.answer not in item.options):
                raise ValueError("Invalid multiple-choice answer")
            if item.type == "true_false" and item.answer.strip().lower() not in {"true", "false"}:
                raise ValueError("Invalid true/false answer")

        material = valid_pages(result.model_dump(), pages)
        document["materials"]["quiz"] = material
        return material
    except Exception as error:
        logger.exception("Quiz generation failed")
        raise HTTPException(
            status_code=503,
            detail="Quiz generation is temporarily unavailable. Please retry in a moment.",
        ) from error


@app.post("/api/study/flashcards")
async def create_flashcards(request: DocumentRequest, session: StudySession = Depends(require_session)) -> dict:
    """Generate a deck of question-and-answer flashcards from the textbook."""
    document = owned_document(session, request.document_id)
    context, pages = document_context(document)
    try:
        async with generation_slots:
            result = await run_in_threadpool(
                generate_structured,
                study_prompt(
                    "revision flashcards", document["filename"], context,
                    "Generate 6 to 20 focused question-and-answer cards with concise answers.",
                ),
                FlashcardsOutput,
            )

        # Validate deck size constraints.
        if not 2 <= len(result.cards) <= 20:
            raise ValueError("Flashcard deck must contain 2 to 20 cards")

        material = valid_pages(result.model_dump(), pages)
        document["materials"]["flashcards"] = material
        return material
    except Exception as error:
        logger.exception("Flashcard generation failed")
        raise HTTPException(
            status_code=503,
            detail="Flashcard generation is temporarily unavailable. Please retry in a moment.",
        ) from error


# ---------------------------------------------------------------------------
# Chat — Ask Lumio
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def ask_lumio(request: ChatRequest, session: StudySession = Depends(require_session)) -> dict:
    """
    Answer a student's question using nearest-neighbor retrieval.

    Pipeline: embed the question → query ChromaDB → filter by distance
    threshold → prompt Gemini with retrieved excerpts and chat history
    → validate source pages → append to conversation history.
    """
    document = owned_document(session, request.document_id)
    try:
        # --- Embed the student's question for vector similarity search ---
        query_embedding = await run_in_threadpool(generate_embedding, request.question, "RETRIEVAL_QUERY")

        # --- Retrieve the nearest document chunks with hybrid reranking ---
        matches = await run_in_threadpool(
            query_chunks,
            session.token,
            request.document_id,
            query_embedding,
            6,
            request.question,
        )

        # --- Filter out chunks that are too distant (low relevance) ---
        matches = [match for match in matches if match["distance"] <= 0.85]
        if not matches:
            answer = "I could not find enough relevant information in this document to answer confidently."
            return {"answer": answer, "source_pages": []}

        # --- Assemble context from matching chunks ---
        context = "\n\n".join(
            f"[Pages {match['metadata']['source_pages']}; {match['metadata']['section']}] {match['text']}"
            for match in matches
        )

        # --- Include recent conversation history for continuity ---
        history = session.chat.setdefault(request.document_id, [])

        async with generation_slots:
            result = await run_in_threadpool(
                generate_structured,
                chat_prompt(request.question, context, history),
                ChatOutput,
            )

        # --- Validate that cited pages actually appear in retrieved chunks ---
        available_pages = {
            int(page)
            for match in matches
            for page in match["metadata"].get("source_pages", "").split(",")
            if page.isdigit()
        }
        response = {
            "answer": result.answer,
            "source_pages": [page for page in result.source_pages if page in available_pages],
        }

        # --- Update conversation history (keep last 12 turns) ---
        history.extend([
            {"role": "student", "content": request.question},
            {"role": "lumio", "content": result.answer},
        ])
        del history[:-12]

        return response
    except Exception as error:
        logger.exception("Textbook question answering failed")
        raise HTTPException(
            status_code=503,
            detail="Ask Lumio tutor is temporarily unavailable. Please retry in a moment.",
        ) from error


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

@app.post("/api/export/pdf")
async def export_pdf(request: ExportRequest, session: StudySession = Depends(require_session)) -> Response:
    """
    Export a previously generated study material as a downloadable PDF.

    The material must already exist in the session's cache (generated via
    one of the study endpoints).
    """
    document = owned_document(session, request.document_id)
    material = document["materials"].get(request.kind)
    if material is None:
        raise HTTPException(status_code=409, detail="Generate this study material before exporting it.")

    try:
        pdf_bytes = await run_in_threadpool(make_pdf, request.kind, material)
    except Exception as error:
        logger.exception("PDF export failed")
        raise HTTPException(status_code=500, detail="PDF export failed. Retry the download.") from error

    filename = f"lumio-{request.kind}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Session ownership is enforced before every document operation.

# Cloudflare Python Workers entrypoint (only available in Cloudflare Pyodide runtime)
try:
    import importlib
    asgi = importlib.import_module("workers.asgi")
    default = asgi.entrypoint(app)
except (ImportError, ModuleNotFoundError):
    default = None

