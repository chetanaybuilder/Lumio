# Fixes Log & Verification Matrix — Lumio

This document tracks every defect identified in [AUDIT.md](file:///d:/Lumio/Lumio/AUDIT.md), the commit/patch where it was resolved, and how each fix was verified.

| Audit ID | Severity | File(s) Modified | Resolution Summary | How Verified |
|---|---|---|---|---|
| **AUDIT-01** | Critical | `backend/app/config.py`<br>`backend/app/groq_client.py` | Configured default models to valid Groq targets (`llama-3.3-70b-versatile` with `llama-3.1-8b-instant` fallback); removed references to nonexistent `gpt-oss-20b`. | Tested Groq client initialization and generation fallback logic. |
| **AUDIT-02** | Critical | `frontend/public/_worker.js`<br>`frontend/functions/api/[[path]].js` | Removed 2,400+ lines of mock edge workers intercepting `/api/*` with synthetic fake chemistry data. | Git removal confirmed; verified Cloudflare Pages serves clean React frontend without mock API intercept. |
| **AUDIT-03** | Critical | `backend/app/pdf_extractor.py` | Replaced naive `get_text("text")` with layout-aware span/block extraction sorted in reading order; preserved subscripts (`H₂O`, `SO₄²⁻`), superscripts (`10⁻³¹`), and Greek letters. | `backend/tests/test_processing.py` and `evals/eval_retrieval.py` (92.1% extraction fidelity across 16 pages). |
| **AUDIT-04** | High | `backend/app/pdf_extractor.py` | Structured tables extracted once as clean Markdown, with bounding boxes excluded from raw text to prevent duplication. | Verified table output contains zero duplicates in extraction tests. |
| **AUDIT-05** | High | `backend/app/pdf_extractor.py` | Page-by-page character density analysis detects individual scanned or unreadable pages and alerts users with clear page numbers. | `backend/tests/test_workflow.py::test_scanned_pdf_upload_is_rejected_with_422`. |
| **AUDIT-06** | Medium | `backend/app/pdf_extractor.py` | Extracted both 0-based page index and printed page labels (`page.get_page_labels()`). | Verified page citations match textbook page numbering. |
| **AUDIT-07** | Critical | `backend/app/text_preprocessor.py` | Replaced destructive transliteration map with scientific Unicode preservation for formulas, Greek symbols (`α, β, γ`), and arrows (`→, ⇌`). | `test_clean_text_normalizes_scientific_symbols_and_encoding` passed. |
| **AUDIT-08** | High | `backend/app/text_preprocessor.py` | Implemented soft-wrap de-hyphenation (`([a-zA-Z])- \n([a-zA-Z])`) and paragraph line-joining. | Spot-checks in extraction eval confirmed hyphenated terms (`molecu-lar`) join correctly. |
| **AUDIT-09** | High | `backend/app/structure_detector.py` | Demoted diagram and table headers so they remain content items rather than shattering real chapter sections. | `test_structure_detector_recognizes_diagrams_tables_and_landmarks` passed. |
| **AUDIT-10** | Critical | `backend/app/chunker.py` | Semantic block-level chunking keeping markdown tables and formulas intact; replaced single-line whitespace flattening. | Verified chunks retain multi-line markdown tables and formula boundaries. |
| **AUDIT-11** | Medium | `backend/app/chunker.py` | Guaranteed progress in chunker sliding window with `step = max(1, chunk_size - overlap)`. | Stress tested with boundary conditions (`chunk_size <= overlap`); no infinite loops. |
| **AUDIT-12** | Critical | `backend/app/embedding_generator.py`<br>`backend/app/vector_store.py` | Replaced 256-dim MD5 hashed n-gram with real dense embeddings (`bge-small-en-v1.5` via FastEmbed/ONNX, 384 dimensions). | Retrieval benchmark achieved 97.62% Hit@1, 100.0% Hit@5, and 0.9881 MRR. |
| **AUDIT-13** | High | `backend/app/vector_store.py` | Added SQLite persistence layer (`lumio_vectors.db`) so server restarts retain indexed textbook documents. | Chunks and metadata persisted across store re-instantiations. |
| **AUDIT-14** | High | `backend/app/vector_store.py` | Implemented BM25 keyword search combined with dense cosine similarity via Reciprocal Rank Fusion (RRF). | Evaluated on 42 textbook queries (`evals/eval_retrieval.py` target: Hit@5 >= 92%, actual: 100%). |
| **AUDIT-15** | Critical | `backend/app/study_engine.py`<br>`backend/app/main.py` | Implemented hierarchical map-reduce study engine to synthesize complete textbooks section by section without truncation. | Rubric evaluation covers 20/20 essential CBSE chemistry curriculum landmarks. |
| **AUDIT-16** | High | `backend/app/study_engine.py` | Removed hardcoded fake placeholder fallback strings; enforced strict Pydantic parsing and validation. | E2E notes generation tests confirm genuine textbook content throughout. |
| **AUDIT-17** | Medium | `backend/app/main.py` | Calibrated RRF and similarity score thresholds for grounded Q&A. | Out-of-domain queries return ungrounded notices instead of hallucinated facts. |
| **AUDIT-18** | Medium | `backend/app/retrieval_utils.py` | Robust, type-safe citation parsing supporting both integer arrays and comma-separated strings. | Verified citation handling on diverse page format outputs. |
| **AUDIT-19** | Low | `backend/app/main.py` | Removed dead/failing Pyodide ASGI stub. | Verified FastAPI startup is clean without worker import errors. |
| **AUDIT-20** | Critical | `backend/app/export_service.py` | Added Unicode font registration (DejaVuSans / LiberationSans / Helvetica fallback) and subscript/superscript translation so chemistry formulas and Greek letters export cleanly without crashing. | `backend/tests/test_workflow.py::test_pdf_export_unicode_subscripts_and_greek` passed with pypdf validation. |
| **AUDIT-21** | Medium | `backend/app/session_manager.py` | Added eager removal of expired sessions upon access to prevent memory leaks. | Verified expired sessions are immediately evicted. |
| **AUDIT-22** | High | `backend/app/prompt_templates.py` | Removed explicit instructions to invent `[check source p.X]`; instructed model to rely strictly on excerpts. | Prompts verified clean; no fabricated tags generated. |
| **AUDIT-23** | Critical | `backend/requirements.txt` | Added `pymupdf>=1.24.0` and `fastembed` dependencies to requirements. | `pip install -r backend/requirements.txt` installs all required packages cleanly. |
| **AUDIT-24** | Low | `backend/tests/conftest.py`<br>`backend/app/config.py` | Removed obsolete `CHROMA_DIR` settings and fixtures. | Verified test suite runs cleanly without Chroma references. |
| **AUDIT-25** | Medium | `frontend/src/App.jsx` | Aligned client file size check to exact 20 MB limit (`20 * 1024 * 1024`). | Verified 21 MB files are caught with clear message before upload attempt. |
| **AUDIT-26** | High | `frontend/src/App.jsx`<br>`frontend/src/api.js` | Added `AbortController` support to cancel in-flight generation requests when switching views or re-uploading. | Clean cancellation verified without uncaught promise errors. |
| **AUDIT-27** | High | `frontend/src/api.js` | Transparent 401 recovery: auto-mints a new session and retries requests once upon session expiration. | Client gracefully recovers from expired tokens without jarring error screens. |
| **AUDIT-28** | Medium | `frontend/src/App.jsx` | Wrapped Ask Lumio chat messages with `<MathText>` so LaTeX formulas and chemistry notation render with KaTeX. | Verified chat messages render formatted math and chemical symbols. |
| **AUDIT-29** | Low | `frontend/src/App.jsx` | Made Table of Contents search input placeholder dynamic based on actual subtopics length (`Search ${subtopics.length} subtopics...`). | UI displays accurate count for any uploaded book. |
| **AUDIT-30** | Low | `frontend/src/api.js` | Removed dead `X-Groq-Api-Key` and `lumio_groq_key` localStorage reads. | Code hygiene verified; no token leakage. |
| **AUDIT-31** | High | `.gitignore` | Ignored large binary PDF files from git tracking. | `git status` clean of duplicate binary PDFs. |
| **AUDIT-32** | High | `README.md`<br>`ARCHITECTURE.md` | Rewrote documentation to reflect actual FastAPI backend + Cloudflare static frontend architecture. | Docs reflect verified production deployment architecture. |

---

## Metric Comparison: Before vs. After

| Metric | Baseline / Before | Rebuilt / After | Target |
|---|---|---|---|
| **Retrieval Hit@1** | 35.7% (MD5 n-grams) | **97.62%** (FastEmbed + BM25) | >= 70% |
| **Retrieval Hit@5** | 64.3% | **100.00%** | >= 92% |
| **Retrieval MRR** | 0.442 | **0.9881** | >= 0.75 |
| **Extraction Fidelity** | ~40% (mangled symbols, tables duplicated) | **92.11%** (35/38 spot snippets) | >= 85% |
| **Notes Curriculum Coverage** | 4/20 landmarks (first 9k chars only) | **20/20 landmarks** (10.0/10) | 20/20 |
| **Notes Factual Faithfulness** | Poor (invented tags, placeholders) | **9.75 / 10.0** | >= 9.0 |
| **Backend Test Suite** | 3 failing / collection error | **19 passed (100%)** | 100% |
| **Frontend Production Build** | Intercepted by mock `_worker.js` | **Clean Vite bundle (455 KB JS)** | Clean build |
