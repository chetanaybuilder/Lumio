
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from tempfile import NamedTemporaryFile
from uuid import uuid4

import pymupdf
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.chunker import create_chunks
from app.config import FRONTEND_ORIGINS, MAX_UPLOAD_BYTES, SESSION_TTL_SECONDS, TEMP_DIR
from app.embedding_generator import generate_embeddings, generate_embedding
from app.export_service import make_pdf
from app.gemini_client import generate_structured
from app.pdf_extractor import PDFPageLimitError, extract_text_from_pdf
from app.prompt_templates import chat_prompt, study_prompt
from app.schemas import (
    ChatOutput,
    ChatRequest,
    DocumentRequest,
    ExportRequest,
    FlashcardsOutput,
    NotesOutput,
    QuizOutput,
    QuizRequest,
)
from app.session_manager import (
    StudySession,
    create_session,
    expired_sessions,
    get_session,
    remove_session,
)
from app.structure_detector import detect_structure
from app.text_preprocessor import clean_pages
from app.vector_store import clear_all_chunks, delete_document, query_chunks, store_chunks


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lumio")
generation_slots = asyncio.Semaphore(2)


async def cleanup_expired_sessions() -> None:
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
    while True:
        await asyncio.sleep(60)
        await cleanup_expired_sessions()


@asynccontextmanager
async def lifespan(_: FastAPI):
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


app = FastAPI(title="Lumio API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Session-Token"],
)


async def require_session(x_session_token: str | None = Header(default=None)) -> StudySession:
    session = await get_session(x_session_token)
    if session is None:
        raise HTTPException(status_code=401, detail="Study session is missing or expired.")
    return session


def owned_document(session: StudySession, document_id: str) -> dict:
    document = session.documents.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found in this study session.")
    return document


def valid_pages(material: dict, allowed_pages: set[int]) -> dict:
    def filter_pages(record: dict) -> None:
        record["source_pages"] = [page for page in record.get("source_pages", []) if page in allowed_pages]

    for section in material.get("sections", []):
        filter_pages(section)
    for item in material.get("questions", material.get("cards", [])):
        filter_pages(item)
    return material


def document_context(document: dict) -> tuple[str, set[int]]:
    excerpts = []
    pages: set[int] = set()
    for chunk in document["chunks"]:
        chunk_pages = chunk.get("source_pages", [])
        pages.update(chunk_pages)
        excerpt = f"[Pages {', '.join(map(str, chunk_pages))}; {chunk.get('section', 'Section')}] {chunk['text']}"
        if sum(map(len, excerpts)) + len(excerpt) > 36000:
            break
        excerpts.append(excerpt)
    return "\n\n".join(excerpts), pages


@app.get("/health")
def health_check() -> dict:
    return {"status": "healthy", "app": "Lumio"}


@app.post("/api/sessions", status_code=201)
async def start_session() -> dict:
    session = await create_session()
    return {"session_token": session.token, "expires_in": SESSION_TTL_SECONDS}


@app.delete("/api/sessions/current", status_code=204)
async def end_session(session: StudySession = Depends(require_session)) -> Response:
    for document_id in session.documents:
        try:
            delete_document(document_id, session.token)
        except Exception as error:
            logger.exception("Session vector cleanup failed")
            raise HTTPException(status_code=503, detail="Session cleanup failed; retry before closing this session.") from error
    await remove_session(session.token)
    return Response(status_code=204)


@app.post("/api/documents/upload", status_code=201)
async def upload_pdf(file: UploadFile = File(...), session: StudySession = Depends(require_session)) -> dict:
    if len(session.documents) >= 5:
        raise HTTPException(status_code=429, detail="A study session can contain up to five documents.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = None
    document_id = uuid4().hex
    total_size = 0
    try:
        with NamedTemporaryFile(mode="wb", suffix=".pdf", dir=TEMP_DIR, delete=False) as temp_file:
            temp_path = temp_file.name
            while content := await file.read(1024 * 1024):
                total_size += len(content)
                if total_size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="PDF exceeds the configured upload limit.")
                temp_file.write(content)
        with open(temp_path, "rb") as saved_file:
            if b"%PDF-" not in saved_file.read(1024):
                raise HTTPException(status_code=400, detail="The uploaded file is not a readable PDF.")

        pages = await run_in_threadpool(extract_text_from_pdf, temp_path)
        cleaned_pages = clean_pages(pages)
        if not any(page["text"] for page in cleaned_pages):
            raise HTTPException(status_code=422, detail="No selectable text found. This PDF may require OCR.")
        sections = detect_structure(cleaned_pages)
        chunks = create_chunks(sections)
        if not chunks or len(chunks) > 1000:
            raise HTTPException(status_code=413, detail="Document is empty or exceeds the processing limit.")
        embeddings = await run_in_threadpool(generate_embeddings, [chunk["text"] for chunk in chunks])
        try:
            await run_in_threadpool(store_chunks, document_id, chunks, embeddings, session.token)
        except Exception:
            try:
                await run_in_threadpool(delete_document, document_id, session.token)
            except Exception:
                logger.exception("Failed to roll back partial document vectors")
            raise
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
        raise HTTPException(status_code=413, detail="PDF exceeds the configured page limit.") from error
    except (pymupdf.FileDataError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Unable to read this PDF. Check that the file is not damaged.") from error
    except RuntimeError as error:
        logger.warning("Document processing could not complete: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="Document processing is temporarily unavailable. Check service configuration and retry.") from error
    except Exception as error:
        logger.exception("Document processing failed")
        raise HTTPException(status_code=502, detail="Document processing failed. Check service configuration and retry.") from error
    finally:
        await file.close()
        if temp_path:
            try:
                import os
                os.unlink(temp_path)
            except OSError:
                logger.warning("Temporary upload cleanup failed")


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str, session: StudySession = Depends(require_session)) -> dict:
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
    owned_document(session, document_id)
    try:
        await run_in_threadpool(delete_document, document_id, session.token)
    except Exception as error:
        logger.exception("Document vector cleanup failed")
        raise HTTPException(status_code=503, detail="Document cleanup failed; retry before ending this session.") from error
    session.documents.pop(document_id, None)
    session.chat.pop(document_id, None)
    return Response(status_code=204)


async def generate_notes(request: DocumentRequest, session: StudySession, kind: str, instructions: str) -> dict:
    document = owned_document(session, request.document_id)
    context, pages = document_context(document)
    try:
        async with generation_slots:
            result = await run_in_threadpool(
                generate_structured,
                study_prompt(kind, document["filename"], context, instructions),
                NotesOutput,
            )
        material = valid_pages(result.model_dump(), pages)
        document["materials"][kind] = material
        return material
    except Exception as error:
        logger.exception("Study material generation failed")
        raise HTTPException(status_code=503, detail="Study generation failed. Check Gemini configuration and retry.") from error


@app.post("/api/study/deep-notes")
async def deep_notes(request: DocumentRequest, session: StudySession = Depends(require_session)) -> dict:
    return await generate_notes(request, session, "deep-notes", "Organize detailed concepts, definitions, formulas, examples, and revision priorities by section.")


@app.post("/api/study/quick-notes")
async def quick_notes(request: DocumentRequest, session: StudySession = Depends(require_session)) -> dict:
    return await generate_notes(request, session, "quick-notes", "Create concise revision sections with essential definitions, formulas, facts, and distinctions.")


@app.post("/api/study/quiz")
async def create_quiz(request: QuizRequest, session: StudySession = Depends(require_session)) -> dict:
    document = owned_document(session, request.document_id)
    context, pages = document_context(document)
    prompt = study_prompt("a quiz", document["filename"], context, f"Generate exactly {request.count} questions at {request.difficulty} difficulty. Mix multiple_choice, true_false, and short_answer question types. Include answer, explanation, and source pages.")
    try:
        async with generation_slots:
            result = await run_in_threadpool(generate_structured, prompt, QuizOutput)
        if len(result.questions) != request.count:
            raise ValueError("Incorrect quiz question count")
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
        raise HTTPException(status_code=503, detail="Quiz generation failed validation or the AI service is unavailable.") from error


@app.post("/api/study/flashcards")
async def create_flashcards(request: DocumentRequest, session: StudySession = Depends(require_session)) -> dict:
    document = owned_document(session, request.document_id)
    context, pages = document_context(document)
    try:
        async with generation_slots:
            result = await run_in_threadpool(
                generate_structured,
                study_prompt("revision flashcards", document["filename"], context, "Generate 6 to 20 focused question-and-answer cards with concise answers."),
                FlashcardsOutput,
            )
        if not 2 <= len(result.cards) <= 20:
            raise ValueError("Flashcard deck must contain 2 to 20 cards")
        material = valid_pages(result.model_dump(), pages)
        document["materials"]["flashcards"] = material
        return material
    except Exception as error:
        logger.exception("Flashcard generation failed")
        raise HTTPException(status_code=503, detail="Flashcard generation failed validation or the AI service is unavailable.") from error


@app.post("/api/chat")
async def ask_lumio(request: ChatRequest, session: StudySession = Depends(require_session)) -> dict:
    document = owned_document(session, request.document_id)
    try:
        query_embedding = await run_in_threadpool(generate_embedding, request.question, "RETRIEVAL_QUERY")
        matches = await run_in_threadpool(query_chunks, session.token, request.document_id, query_embedding)
        matches = [match for match in matches if match["distance"] <= 0.85]
        if not matches:
            answer = "I could not find enough relevant information in this document to answer confidently."
            return {"answer": answer, "source_pages": []}
        context = "\n\n".join(
            f"[Pages {match['metadata']['source_pages']}; {match['metadata']['section']}] {match['text']}"
            for match in matches
        )
        history = session.chat.setdefault(request.document_id, [])
        async with generation_slots:
            result = await run_in_threadpool(
                generate_structured,
                chat_prompt(request.question, context, history),
                ChatOutput,
            )
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
        history.extend([
            {"role": "student", "content": request.question},
            {"role": "lumio", "content": result.answer},
        ])
        del history[:-12]
        return response
    except Exception as error:
        logger.exception("Textbook question answering failed")
        raise HTTPException(status_code=503, detail="Ask Lumio is temporarily unavailable. Check Gemini configuration and retry.") from error


@app.post("/api/export/pdf")
async def export_pdf(request: ExportRequest, session: StudySession = Depends(require_session)) -> Response:
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
