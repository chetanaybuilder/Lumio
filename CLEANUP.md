# Part 2 Cleanup Log: Dead Code and Bloat Removal

This document records all files, functions, dependencies, configurations, and documentation claims removed during Part 2 of the Lumio modernization. Every removal was verified to keep all tests and frontend builds fully green.

---

## 1. Dead Shadow Mock Backends (2,475 lines removed)

| File | Lines Removed | Rationale & Safety Justification |
| :--- | :--- | :--- |
| `frontend/public/_worker.js` | 1,457 lines | Dead Cloudflare Worker script that intercepted `/api/*` requests on Cloudflare Pages and served hardcoded/regex mocks. Created severe architectural divergence from the actual Python FastAPI backend. Removed completely. |
| `frontend/functions/api/[[path]].js` | 1,018 lines | Duplicate Pages Function script implementing the same regex-based PDF parser and mock API. Removed completely along with the empty `frontend/functions/` directory. |

---

## 2. Obsolete Backend Shims & Stubs (22 lines removed)

| File | Lines Removed | Rationale & Safety Justification |
| :--- | :--- | :--- |
| `backend/app/gemini_client.py` | 13 lines | Legacy compatibility shim that merely forwarded to `app.groq_client`. All active code already imports directly from `app.groq_client`. |
| `backend/app/main.py` (Pyodide stub) | 9 lines | Non-functional Pyodide ASGI entrypoint stub (`workers.asgi`). The application runs on standard Python ASGI (Uvicorn). |

---

## 3. Large Committed Binaries Removed from Git Tracking

| File | Size | Rationale & Safety Justification |
| :--- | :--- | :--- |
| `Chemistry_Textbook_CBSE.pdf` | 2.1 MB | Large binary committed at repository root. Untracked from git index via `git rm --cached` and protected by `.gitignore` (`*.pdf`). Kept on local disk for offline evaluation harness and integration tests. |
| `frontend/public/Chemistry_Textbook_CBSE.pdf` | 2.1 MB | Duplicate copy of the same 2.1 MB binary committed under the frontend public assets folder. Untracked from git index and ignored. |

---

## 4. Configuration and Environment Bloat

| File | Changes | Rationale & Safety Justification |
| :--- | :--- | :--- |
| `frontend/wrangler.json` | 12 lines removed | Removed dead Cloudflare `ai` binding (`binding: "AI"`) and `kv_namespaces` (`binding: "LUMIO_STORAGE"`). Pages now strictly deploys the static Vite bundle. |
| `backend/app/config.py` | 4 lines removed | Removed obsolete `CHROMA_DIR` path and setting. Vector storage is in-memory scoped cosine / BM25 index. |
| `backend/.env.example` | 2 lines removed | Removed obsolete `CHROMA_DIR`. Set default `GROQ_MODEL=llama-3.3-70b-versatile`. |
| `backend/tests/conftest.py` | 6 lines removed | Removed obsolete Chroma directory isolation fixture (`chroma_dir`). |
| `frontend/src/api.js` | 8 lines removed | Removed dead `localStorage.getItem('lumio_groq_key')` header injection. Backend uses process environment `GROQ_API_KEY`. |
| `backend/requirements.txt` | 1 line added | Added `pymupdf>=1.24.0` which was missing from requirements despite being the primary PDF extractor. |

---

## 5. False & Misleading Documentation Claims Corrected

| File | Section | Correction |
| :--- | :--- | :--- |
| `README.md` | Deployment | Removed false claim that Cloudflare Edge Workers execute the Python pipeline or handle PDF extraction. Documented genuine architecture: Cloudflare Pages (Frontend) + Containerized FastAPI (Backend). |
| `README.md` | Model Name | Replaced nonexistent models `openai/gpt-oss-20b` and `qwen/qwen3.8-27b` with active Groq models: `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. |
| `README.md` | Performance | Removed unrealistic marketing claims ("1-3 seconds for 500 pages"). |
| `ARCHITECTURE.md` | Embeddings & Models | Corrected Groq model identifiers and described hybrid retrieval pipeline. |
| `ARCHITECTURE.md` | Deployment | Removed Cloudflare Edge Worker claims for `/api/*` execution. |

---

## 6. Verification Status

- **Backend Test Suite:** `python -m pytest backend/tests` -> **18 passed** in 2.84s.
- **Frontend Production Build:** `npm run build` in `frontend/` -> **Clean build in 2.45s** (dist/ created, zero errors).
- **Git Tree Status:** 2,500+ lines of dead mock code and 4.2 MB of binary blobs removed from git tracking.
