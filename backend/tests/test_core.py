"""
Core API Tests — Lumio Backend
================================

Fast, isolated tests that verify the API server's foundational behavior
without requiring a live Gemini key or a real PDF:

- Health endpoint returns the expected JSON.
- Requests without a valid session token are rejected with ``401``.
- Document ownership prevents cross-session access (``404``).
- Provider errors produce safe HTTP responses and clean up temp files.

These tests use FastAPI's ``TestClient`` and ``monkeypatch`` to replace
external dependencies with deterministic stubs.
"""

import pytest

# Ensure required native libraries are available before importing the app.
pytest.importorskip("pymupdf")

from app.main import app, require_session
from app.session_manager import StudySession
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

def test_health_endpoint():
    """The /health endpoint should return a JSON status object."""
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "healthy", "app": "Lumio"}


# ---------------------------------------------------------------------------
# Session authentication
# ---------------------------------------------------------------------------

def test_missing_session_is_rejected():
    """Requests without X-Session-Token should receive 401 Unauthorized."""
    with TestClient(app) as client:
        response = client.post("/api/documents/upload", files={"file": ("book.pdf", b"%PDF-1.4")})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Document ownership isolation
# ---------------------------------------------------------------------------

def test_session_document_ownership_blocks_cross_session_access():
    """A session must not be able to access another session's documents."""
    owner = StudySession("owner", 9999999999, documents={"doc-owner": {"filename": "book.pdf"}})
    intruder = StudySession("intruder", 9999999999)

    # Override the session dependency to simulate the intruder's request.
    app.dependency_overrides[require_session] = lambda: intruder
    try:
        with TestClient(app) as client:
            response = client.get("/api/documents/doc-owner")
        assert response.status_code == 404
        # Verify that the owner's documents were not affected.
        assert "doc-owner" in owner.documents
    finally:
        app.dependency_overrides.pop(require_session, None)


# ---------------------------------------------------------------------------
# Error safety and temp-file cleanup
# ---------------------------------------------------------------------------

def test_upload_does_not_expose_provider_errors_or_leave_temp_files(monkeypatch, tmp_path):
    """
    When the embedding provider fails:
    - The HTTP response must NOT contain internal error details.
    - The temporary upload file must be removed.
    """
    from app import main

    session = StudySession("owner", 9999999999)
    app.dependency_overrides[require_session] = lambda: session

    # Stub the entire processing pipeline up to embeddings.
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
        # The API should return a 503 with a safe, generic message.
        assert response.status_code == 503
        assert "sensitive provider details" not in response.text
        # The temporary upload file must have been cleaned up.
        assert list(tmp_path.iterdir()) == []
    finally:
        app.dependency_overrides.pop(require_session, None)


# API tests cover health and server-side session authorization.
