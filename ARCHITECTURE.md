# Architecture

## Request and document flow

The React client creates a temporary session and sends its opaque `X-Session-Token` on every API operation. PDF upload streams to a server-generated temporary path, checks the suffix, signature, byte/page limits, extracts selectable text with PyMuPDF, normalizes whitespace, detects headings, forms overlapping chunks with source-page metadata, creates fast local normalized embeddings, and writes the vectors to the in-memory vector store. Temporary upload files are removed after processing.

The cleaner preserves text. The structure detector is heuristic; headings that do not match its patterns remain ordinary content. Page references are extracted page numbers, not a guarantee that the source's printed page labels match the PDF viewer's page count.

## Embeddings and retrieval

The centralized Groq client uses `llama-3.3-70b-versatile` (with `llama-3.1-8b-instant` as fallback) on Groq LPUs for high-speed, high-quality structured text generation. Local semantic and keyword embeddings provide dense and sparse vectors without external embedding rate limits. Cosine distance and BM25 are fused with Reciprocal Rank Fusion for nearest-neighbor similarity search. Every vector stores `session_id`, `document_id`, section, and source pages. Queries require both session and document filters; deletion uses both as well. A section-aware map-reduce pipeline is used for note generation, while Ask Lumio retrieves the nearest chunks and rejects matches below a calibrated similarity threshold.

## Generation and validation

Prompt templates explicitly treat uploaded text as untrusted reference material. Structured Groq responses are validated by Pydantic models for notes, quiz questions, cards, and chat answers. The API removes generated source-page claims not present in the document. Quiz count, answer membership, type, and choice constraints are checked before returning output. Provider, malformed-response, and validation errors return safe HTTP errors rather than fabricated study material.

## Session lifecycle and privacy

Session tokens use `secrets.token_urlsafe` and are held in memory with sliding one-hour inactivity expiry. Each document and material cache is reachable only through its owning session record. Expired sessions are periodically removed and their records are logically deleted. Explicit session deletion follows the same path. The client stores its token in tab-scoped `sessionStorage` so refresh does not discard a valid session, and offers a fresh-session action.

This is a single-process MVP: session records and generated study outputs are not shared across workers or persisted for restart. Run one backend worker. Logical deletion does not prove physical erasure from database files, SSDs, backups, or filesystem snapshots. Cleanup failures are logged, but operational monitoring/retry queues are not yet provided. Browser tab closure cannot be observed reliably; TTL cleanup is the fallback.

The upload route enforces its byte limit while copying the parsed multipart file into a temporary file. Starlette may already have received and spooled the multipart body before that route-level check runs; production ingress must also enforce a request-body limit. There is no distributed or per-session rate limiter yet, and session creation is public, so this MVP needs an upstream abuse-control layer before unrestricted public exposure.

Extracted document excerpts are sent to Groq's high-speed inference API for generated study materials or answers. Chat requests also send the student's question and a short recent conversation history. Provider-side handling and retention are governed by Groq's terms and configuration; Lumio does not log document text intentionally.

## PDF exports

Validated structured materials are rendered with ReportLab into `BytesIO`; no user-controlled HTML or temporary export files are used. Export types are notes, quiz, and printable flashcards. The response is an attachment with a server-selected filename. Default ReportLab fonts support basic Unicode imperfectly; font embedding can be added for broader glyph coverage.

## API contract

All endpoints except `/health` and session creation require `X-Session-Token`.

| Method | Path | Input | Response |
|---|---|---|---|
| GET | `/health` | none | status and app name |
| POST | `/api/sessions` | none | `session_token`, `expires_in` |
| DELETE | `/api/sessions/current` | token header | 204 |
| POST | `/api/documents/upload` | multipart PDF | document ID, name, page/chunk counts, ready status |
| GET | `/api/documents/{document_id}` | token header | owned document metadata |
| DELETE | `/api/documents/{document_id}` | token header | 204 |
| POST | `/api/study/deep-notes` | `document_id` | title and sourced sections |
| POST | `/api/study/quick-notes` | `document_id` | title and concise sections |
| POST | `/api/study/quiz` | `document_id`, optional count and difficulty | title and validated questions |
| POST | `/api/study/flashcards` | `document_id` | title and sourced cards |
| POST | `/api/chat` | `document_id`, question | answer and retrieved source pages |
| POST | `/api/export/pdf` | `document_id`, kind | PDF attachment |

The browser uses Vite's `/api` proxy locally. Production deployments configure `VITE_API_BASE_URL`; backend CORS origins are controlled by `FRONTEND_ORIGINS`.
 
## Deployment
 
The application frontend is deployed to Cloudflare Pages (`lumio-study.pages.dev`) for global static CDN delivery. The backend is deployed as a containerized FastAPI service on a cloud provider (such as Fly.io, Render, or Railway) with access to PyMuPDF and Groq API.

