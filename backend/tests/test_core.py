import pytest

pytest.importorskip("pymupdf")
pytest.importorskip("google.genai")
pytest.importorskip("chromadb")

from app.main import app, require_session
from app.session_manager import StudySession
from fastapi.testclient import TestClient


def test_health_endpoint():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "healthy", "app": "Lumio"}


def test_missing_session_is_rejected():
    with TestClient(app) as client:
        response = client.post("/api/documents/upload", files={"file": ("book.pdf", b"%PDF-1.4")})
    assert response.status_code == 401


def test_session_document_ownership_blocks_cross_session_access():
    owner = StudySession("owner", 9999999999, documents={"doc-owner": {"filename": "book.pdf"}})
    intruder = StudySession("intruder", 9999999999)
    app.dependency_overrides[require_session] = lambda: intruder
    try:
        with TestClient(app) as client:
            response = client.get("/api/documents/doc-owner")
        assert response.status_code == 404
        assert "doc-owner" in owner.documents
    finally:
        app.dependency_overrides.pop(require_session, None)


def test_upload_does_not_expose_provider_errors_or_leave_temp_files(monkeypatch, tmp_path):
    import app.main as main

    session = StudySession("owner", 9999999999)
    app.dependency_overrides[require_session] = lambda: session
    monkeypatch.setattr(main, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(main, "extract_text_from_pdf", lambda _: [{"page": 1, "text": "Lesson text"}])
    monkeypatch.setattr(main, "clean_pages", lambda pages: pages)
    monkeypatch.setattr(main, "detect_structure", lambda pages: [{"heading": "Lesson", "text": "Lesson text"}])
    monkeypatch.setattr(main, "create_chunks", lambda sections: [{"text": "Lesson text", "source_pages": [1]}])

    def fail_embedding(*_args):
        raise RuntimeError("sensitive provider details")

    monkeypatch.setattr(main, "generate_embeddings", fail_embedding)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/documents/upload",
                headers={"X-Session-Token": session.token},
                files={"file": ("lesson.pdf", b"%PDF-1.4 content", "application/pdf")},
            )
        assert response.status_code == 503
        assert "sensitive provider details" not in response.text
        assert list(tmp_path.iterdir()) == []
    finally:
        app.dependency_overrides.pop(require_session, None)


# API tests cover health and server-side session authorization.
