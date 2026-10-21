# Lumio

Lumio turns a textbook PDF into sourced study notes, quiz practice, flashcards, and a textbook-grounded chat. It works without accounts; each browser tab receives an expiring temporary study session.

## Stack and structure

- `backend/`: FastAPI, PyMuPDF, Gemini, ChromaDB, Pydantic, ReportLab, and pytest.
- `frontend/`: React and Vite, with a responsive study workspace.
- `ARCHITECTURE.md`: processing, API, isolation, and retention details.

## Prerequisites

- Python 3.11 or newer.
- Node.js 20 or newer and npm.
- A Gemini API key for upload embedding, study generation, and question answering. Health, frontend build, and pure document-processing tests do not require a key.

## Configure and run

From the repository root, create `backend/.env` from `backend/.env.example` and set `GEMINI_API_KEY`. The backend reads process environment variables; load the file with your preferred environment manager or enter the values in your shell.

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY = "your-key"
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`. The development proxy forwards `/api` calls to `http://127.0.0.1:8000`. For a separate backend origin, set `VITE_API_BASE_URL` in `frontend/.env` and include that origin in `FRONTEND_ORIGINS`.

## Tests and production build

```powershell
cd backend
pytest -q
```

```powershell
cd frontend
npm run build
npm run preview
```

The default text-generation model is `gemini-3.8-flash`, currently listed by Google as a stable Flash model with free-tier access. Set `GEMINI_MODEL` to select another supported text model. The embedding model remains `gemini-embedding-001`, configured at 768 dimensions with document/query retrieval task types. Never commit `.env` files or API keys.

## Limits and deployment notes

Defaults cap uploads at 20 MB, 500 pages, five documents per session, and 1,000 chunks per document. The application checks the upload byte limit while copying the parsed multipart file; configure a request-body limit at the reverse proxy or hosting ingress too, since multipart parsing occurs before the route runs. Sessions expire after one hour of inactivity. Use a single Uvicorn worker: session records and generated materials are process-local, while vectors persist under `backend/.chroma`. For multi-worker or multi-instance deployment, replace the in-memory registry/material cache with a shared TTL store and add per-session quotas/rate limiting. There is no built-in request rate limiter yet. Persistent vector deletion is logical Chroma deletion and is not a claim of physical erasure from storage media or backups.

The backend clears its Chroma collection on startup because session ownership records are process-local; uploaded documents and generated materials do not survive a backend restart. Extracted document text is sent to Google's Gemini API for embeddings and generation, along with the student's question and limited recent chat history when using Ask Lumio. Review Google's current data-handling terms before sending sensitive material. The existing Python backend requires a conventional service with compatible dependencies and persistent storage; Cloudflare Pages can host the static frontend, but Pages/Workers are not a drop-in runtime for this backend. See `ARCHITECTURE.md` for the verified constraints.

Scanned image PDFs without selectable text require OCR; OCR is not included. The frontend session token is stored in tab-scoped `sessionStorage` for refresh continuity, and explicit “Start fresh” closes the old session on the server. Closing the browser tab is not a guaranteed immediate signal to the server; expiry cleanup is the fallback. Live Gemini calls require a valid key, network access, and provider availability. No live provider test is run as part of ordinary pytest.

## API overview

- `GET /health`
- `POST /api/sessions`, `DELETE /api/sessions/current`
- `POST /api/documents/upload`, `GET /api/documents/{document_id}`, `DELETE /api/documents/{document_id}`
- `POST /api/study/deep-notes`, `/api/study/quick-notes`, `/api/study/quiz`, `/api/study/flashcards`
- `POST /api/chat`
- `POST /api/export/pdf`

All document operations require `X-Session-Token`. Detailed request/response formats are described in `ARCHITECTURE.md` and FastAPI's `/docs` page.

<!-- Keep setup instructions aligned with the shipped contracts. -->
