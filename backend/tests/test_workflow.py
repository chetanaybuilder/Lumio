"""
Workflow Tests — Lumio Backend
================================

Integration tests that exercise the full user journey:

1. Create sessions.
2. Upload real (generated) PDFs.
3. Verify cross-session isolation.
4. Generate notes, quiz, flashcards, and chat responses.
5. Export each material type as a PDF.
6. Delete documents and sessions.

All Groq calls are stubbed with deterministic fixtures so the tests
run without a live API key.  PDF files are synthesized via PyMuPDF with
realistic educational content to exercise the extraction + chunking
pipeline on real document structure.
"""


import pymupdf
from app.embedding_generator import EMBEDDING_DIMENSIONS
from app.main import app, require_session
from app.schemas import ChatOutput, FlashcardsOutput, NotesOutput, QuizOutput
from app.session_manager import StudySession
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Test PDF content — realistic biology and science material
# ---------------------------------------------------------------------------

PDF_CONTENT = {
    "lumio-test-foundations.pdf": [
        (
            "Cellular energy",
            "Cells transform energy through metabolism. ATP transfers usable energy between cellular processes. Photosynthesis captures light energy in chloroplasts and stores it in glucose; cellular respiration releases energy from glucose to produce ATP.",
            "Mitochondria perform most aerobic respiration. Glycolysis begins in the cytoplasm, while later stages occur in mitochondria. Oxygen is the final electron acceptor in aerobic respiration, producing water. Fermentation regenerates NAD+ when oxygen is unavailable.",
        ),
        (
            "Ecosystem interactions",
            "Producers capture energy, consumers obtain it by eating organisms, and decomposers recycle nutrients. Food webs connect multiple food chains. Energy decreases at each trophic transfer because organisms use energy for metabolism and release heat.",
            "A population is members of one species in an area. A community includes interacting populations. An ecosystem includes the community and nonliving conditions. Biodiversity can improve ecosystem resilience, although disturbances and habitat loss can reduce it.",
        ),
    ],
    "lumio-test-data-tables.pdf": [
        (
            "Experimental design",
            "A controlled experiment changes an independent variable and measures a dependent variable while holding other conditions constant. A control group provides a baseline. Repeated trials reduce the influence of random variation.",
            "Correlation describes association, not necessarily causation. A larger sample may improve precision when it is representative. Researchers should report methods and uncertainty so other researchers can evaluate and reproduce results.",
        ),
        (
            "Measurements",
            "The metric system uses powers of ten. Density equals mass divided by volume. Speed equals distance divided by elapsed time. Mean is the sum divided by the number of observations; median is the middle value after sorting.",
        ),
    ],
}


# ---------------------------------------------------------------------------
# PDF generation helper
# ---------------------------------------------------------------------------

def _make_pdf(path, sections):
    """
    Create a synthetic PDF with the given heading + paragraph sections.

    Each section becomes a new page with a heading and wrapped paragraph
    text, producing a document that exercises PyMuPDF's text extraction.
    """
    document = pymupdf.open()
    for heading, *paragraphs in sections:
        page = document.new_page()
        page.insert_text((72, 72), heading, fontsize=18)
        y = 110
        for text in paragraphs:
            for offset in range(0, len(text), 85):
                page.insert_text((72, y), text[offset:offset + 85], fontsize=11)
                y += 16
    document.save(path)
    document.close()


# ---------------------------------------------------------------------------
# Deterministic Gemini stubs
# ---------------------------------------------------------------------------

def _embedding(*_args, **_kwargs):
    """Return a fixed 768-dimensional vector for any single text."""
    return [0.01] * EMBEDDING_DIMENSIONS


def _embeddings(texts):
    """Return fixed 768-dimensional vectors for a batch of texts."""
    return [[0.01] * EMBEDDING_DIMENSIONS for _ in texts]


def _generated(_prompt, output_type):
    """
    Return a deterministic Pydantic model instance for each output type.

    This stub covers NotesOutput, QuizOutput, FlashcardsOutput, and
    ChatOutput with realistic but fixed content.
    """
    if output_type is NotesOutput:
        return output_type.model_validate({
            "title": "Energy and cells",
            "sections": [{"heading": "ATP", "content": "ATP transfers usable energy between cell processes.", "source_pages": [1]}],
        })
    if output_type is QuizOutput:
        return output_type.model_validate({
            "title": "Energy quiz",
            "questions": [
                {"type": "multiple_choice", "question": f"Question {index}?", "options": ["ATP", "DNA"], "answer": "ATP", "explanation": "The text identifies ATP as an energy carrier.", "difficulty": "medium", "source_pages": [1]}
                for index in range(3)
            ],
        })
    if output_type is FlashcardsOutput:
        return output_type.model_validate({
            "title": "Energy cards",
            "cards": [
                {"front": "What transfers usable energy?", "back": "ATP", "source_pages": [1]},
                {"front": "Where does glycolysis begin?", "back": "In the cytoplasm", "source_pages": [2]},
            ],
        })
    if output_type is ChatOutput:
        return output_type.model_validate({"answer": "ATP transfers usable energy between cellular processes.", "source_pages": [1]})
    raise AssertionError(f"Unexpected output schema: {output_type}")


# ---------------------------------------------------------------------------
# Upload helper
# ---------------------------------------------------------------------------

def _upload(client, token, filename, pdf_dir):
    """Upload a test PDF file through the API with the given session token."""
    return client.post(
        "/api/documents/upload",
        headers={"X-Session-Token": token},
        files={"file": (filename, (pdf_dir / filename).read_bytes(), "application/pdf")},
    )


# ---------------------------------------------------------------------------
# Full workflow integration test
# ---------------------------------------------------------------------------

def test_real_pdf_workflows_isolation_generation_and_exports(monkeypatch, tmp_path):
    """
    End-to-end test: upload → isolation check → generate all materials
    → export PDFs → delete documents → close sessions.
    """
    from app import main

    # Generate synthetic test PDFs.
    for filename, sections in PDF_CONTENT.items():
        _make_pdf(tmp_path / filename, sections)

    # Replace Gemini calls with deterministic stubs.
    monkeypatch.setattr(main, "generate_embeddings", _embeddings)
    monkeypatch.setattr(main, "generate_embedding", _embedding)
    monkeypatch.setattr(main, "generate_structured", _generated)

    with TestClient(app) as client:
        # --- Create two independent sessions ---
        token = client.post("/api/sessions").json()["session_token"]
        other_token = client.post("/api/sessions").json()["session_token"]

        # --- Upload documents to the first session ---
        first = _upload(client, token, "lumio-test-foundations.pdf", tmp_path)
        second = _upload(client, token, "lumio-test-data-tables.pdf", tmp_path)

        assert first.status_code == second.status_code == 201
        first_doc = first.json()
        second_doc = second.json()
        assert first_doc["page_count"] >= 2
        assert second_doc["page_count"] >= 2
        assert first_doc["chunks_created"] > 0
        assert second_doc["chunks_created"] > 0

        document_id = first_doc["document_id"]

        # --- Verify cross-session isolation ---
        assert client.get(
            f"/api/documents/{document_id}",
            headers={"X-Session-Token": other_token},
        ).status_code == 404

        # --- Generate all study materials ---
        headers = {"X-Session-Token": token}
        payload = {"document_id": document_id}

        for path in ("deep-notes", "quick-notes"):
            response = client.post(f"/api/study/{path}", headers=headers, json=payload)
            assert response.status_code == 200
            assert response.json()["sections"][0]["source_pages"] == [1]

        quiz = client.post("/api/study/quiz", headers=headers, json={**payload, "count": 3})
        flashcards = client.post("/api/study/flashcards", headers=headers, json=payload)
        chat = client.post("/api/chat", headers=headers, json={**payload, "question": "What transfers usable energy?"})

        assert quiz.status_code == flashcards.status_code == chat.status_code == 200
        assert len(quiz.json()["questions"]) == 3
        assert len(flashcards.json()["cards"]) == 2
        assert chat.json()["source_pages"] == [1]

        # --- Export each material type as a PDF ---
        for kind in ("deep-notes", "quick-notes", "quiz", "flashcards"):
            exported = client.post("/api/export/pdf", headers=headers, json={**payload, "kind": kind})
            assert exported.status_code == 200
            assert exported.headers["content-type"] == "application/pdf"
            assert exported.content.startswith(b"%PDF-")

        # --- Cleanup: delete document and close session ---
        assert client.delete(f"/api/documents/{document_id}", headers=headers).status_code == 204
        assert client.get(f"/api/documents/{document_id}", headers=headers).status_code == 404
        assert client.delete("/api/sessions/current", headers={"X-Session-Token": other_token}).status_code == 204


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

def test_invalid_pdf_is_rejected_and_temporary_file_is_removed(monkeypatch, tmp_path):
    """Non-PDF files should be rejected with 400 and no temp file left behind."""
    from app import main

    monkeypatch.setattr(main, "TEMP_DIR", tmp_path)
    session = StudySession("test-token", 9999999999)
    app.dependency_overrides[require_session] = lambda: session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/documents/upload",
                headers={"X-Session-Token": session.token},
                files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
            )
        assert response.status_code == 400
        assert list(tmp_path.iterdir()) == []
    finally:
        app.dependency_overrides.pop(require_session, None)


def test_oversized_upload_is_rejected_before_pdf_parsing(monkeypatch, tmp_path):
    """Files exceeding MAX_UPLOAD_BYTES should be rejected with 413."""
    from app import main

    monkeypatch.setattr(main, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 8)
    session = StudySession("test-token", 9999999999)
    app.dependency_overrides[require_session] = lambda: session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/documents/upload",
                headers={"X-Session-Token": session.token},
                files={"file": ("oversized.pdf", b"%PDF-1.4 and more", "application/pdf")},
            )
        assert response.status_code == 413
        assert list(tmp_path.iterdir()) == []
    finally:
        app.dependency_overrides.pop(require_session, None)


def test_scanned_pdf_upload_is_rejected_with_422(monkeypatch, tmp_path):
    """A scanned photograph PDF with no selectable text must return 422 with actionable details."""
    from app import main

    monkeypatch.setattr(main, "TEMP_DIR", tmp_path)
    session = StudySession("test-token", 9999999999)
    app.dependency_overrides[require_session] = lambda: session

    # Synthesize a scanned PDF (image only, no text)
    scanned_path = tmp_path / "scanned.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), 1)
    page.insert_image(pymupdf.Rect(50, 50, 200, 200), pixmap=pix)
    doc.save(str(scanned_path))
    doc.close()

    try:
        with TestClient(app) as client, open(scanned_path, "rb") as f:
            response = client.post(
                "/api/documents/upload",
                headers={"X-Session-Token": session.token},
                files={"file": ("scanned.pdf", f.read(), "application/pdf")},
            )
        assert response.status_code == 422
        assert "scanned" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(require_session, None)


def test_pdf_export_all_materials_integrity():
    """Verify that export_service generates valid, readable PDFs for all 4 study materials."""
    from app.export_service import make_pdf

    notes_mat = {
        "title": "CBSE Chemistry Deep Notes",
        "sections": [
            {"heading": "1.1 Atomic Structure", "content": "Electrons orbit the nucleus in quantized energy levels.", "source_pages": [1, 2]},
            {"heading": "1.2 Chemical Bonding", "content": "Ionic and covalent bonds minimize electrostatic potential energy.", "source_pages": [3]},
        ],
    }
    quiz_mat = {
        "title": "Chemistry Quiz",
        "questions": [
            {
                "type": "multiple_choice",
                "question": "What is the bond angle of methane (CH4)?",
                "options": ["90°", "109.5°", "120°", "180°"],
                "answer": "109.5°",
                "explanation": "Methane has sp3 tetrahedral geometry with 109.5° bond angle.",
                "source_pages": [4],
            }
        ],
    }
    flashcards_mat = {
        "title": "Chemistry Flashcards",
        "cards": [
            {"front": "Define Aufbau principle", "back": "Electrons fill lower energy orbitals first before higher ones.", "source_pages": [2]}
        ],
    }

    for kind, mat in [("deep-notes", notes_mat), ("quick-notes", notes_mat), ("quiz", quiz_mat), ("flashcards", flashcards_mat)]:
        pdf_bytes = make_pdf(kind, mat)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 500
        assert pdf_bytes.startswith(b"%PDF-")

