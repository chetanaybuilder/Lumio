# Architecture

## Request and document flow

The React client creates a temporary session and sends its opaque `X-Session-Token` on every API operation. PDF upload streams to a server-generated temporary path, checks the suffix, signature, byte/page limits, extracts selectable text with PyMuPDF, normalizes whitespace, detects headings, forms overlapping chunks with source-page metadata, creates Gemini embeddings, and writes the vectors to ChromaDB. Temporary upload files are removed after processing.

The cleaner preserves text. The structure detector is heuristic; headings that do not match its patterns remain ordinary content. Page references are extracted page numbers, not a guarantee that the source's printed page labels match the PDF viewer's page count.

## Embeddings and retrieval

The centralized Gemini client uses `gemini-3.8-flash` for text generation and `gemini-embedding-001` at 768 dimensions for vectors. Google currently lists the stable Flash model on its free tier. Document vectors use `RETRIEVAL_DOCUMENT`; question vectors use `RETRIEVAL_QUERY`. Chroma uses cosine distance. Every vector stores `session_id`, `document_id`, section, and source pages. Queries require both session and document filters; deletion uses both as well. A text-only document context is used for note generation, while Ask Lumio retrieves the nearest six chunks and rejects distant matches.

## Generation and validation

Prompt templates explicitly treat uploaded text as untrusted reference material. Structured Gemini responses are validated by Pydantic models for notes, quiz questions, cards, and chat answers. The API removes generated source-page claims not present in the document. Quiz count, answer membership, type, and choice constraints are checked before returning output. Provider, malformed-response, and validation errors return safe HTTP errors rather than fabricated study material.

## Session lifecycle and privacy

Session tokens use `secrets.token_urlsafe` and are held in process memory with sliding one-hour inactivity expiry. Each document and material cache is reachable only through its owning session record. Expired sessions are periodically removed and their Chroma records are logically deleted. Explicit session deletion follows the same path. The client stores its token in tab-scoped `sessionStorage` so refresh does not discard a valid session, and offers a fresh-session action.

This is a single-process MVP: session records and generated study outputs are not shared across workers or persisted for restart. Run one backend worker. At startup, the current implementation clears the Chroma collection because its matching in-memory session records no longer exist; documents and generated materials therefore do not survive a backend restart. Logical deletion does not prove physical erasure from database files, SSDs, backups, or filesystem snapshots. Cleanup failures are logged, but operational monitoring/retry queues are not yet provided. Browser tab closure cannot be observed reliably; TTL cleanup is the fallback.

The upload route enforces its byte limit while copying the parsed multipart file into a temporary file. Starlette may already have received and spooled the multipart body before that route-level check runs; production ingress must also enforce a request-body limit. There is no distributed or per-session rate limiter yet, and session creation is public, so this MVP needs an upstream abuse-control layer before unrestricted public exposure.

The PDF file is processed on the backend, but extracted document text is sent to Google's Gemini API for embeddings and for generated study materials or answers. Chat requests also send the student's question and a short recent conversation history. Provider-side handling and retention are governed by Google's terms and configuration, not Lumio; operators should review those terms before handling sensitive documents. Lumio does not log document text intentionally.

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

The browser uses Vite's `/api` proxy locally. Production deployments can set `VITE_API_BASE_URL`; backend CORS origins are controlled by `FRONTEND_ORIGINS`.

## Deployment constraints

Vite's static frontend can be hosted on Cloudflare Pages. The existing backend is not a direct fit for Pages or Workers: it depends on FastAPI, PyMuPDF, ChromaDB's persistent local filesystem, in-memory sessions, and synchronous PDF/AI work. A reliable deployment needs a conventional Python service with a writable persistent volume (or a deliberate storage/runtime redesign), then the Pages frontend can call that service over HTTPS. Do not deploy this backend to an ephemeral serverless filesystem and assume documents or vectors persist. This repository currently contains no deployment configuration; production URLs and account access must be verified at deployment time.

<!-- Isolation is an authorization boundary, not a client-side convention. -->
