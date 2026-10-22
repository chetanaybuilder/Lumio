/**
 * API Client — Lumio Frontend
 * ============================
 *
 * Centralizes all HTTP communication with the Lumio backend API.
 * Every request passes through a shared `request()` helper that:
 *
 * 1. Attaches the `X-Session-Token` header for authenticated calls.
 * 2. Sets `Content-Type: application/json` for non-FormData bodies.
 * 3. Parses error responses and throws descriptive `Error` objects.
 * 4. Returns `null` for 204 No Content responses (e.g., DELETE).
 *
 * The API base URL defaults to the current origin (same-domain proxy
 * in development) but can be overridden via `VITE_API_BASE_URL` for
 * production deployments where the backend runs on a separate host.
 */

/** Base URL for all API requests — empty string uses the Vite dev proxy. */
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

/**
 * Execute an authenticated API request with error handling.
 *
 * @param {string} path    - API endpoint path (e.g., '/api/sessions').
 * @param {string} token   - Session token for the X-Session-Token header.
 * @param {object} options - Fetch options (method, body, headers, etc.).
 * @returns {Promise<Response|null>} The fetch Response, or null for 204.
 * @throws {Error} With the server's `detail` message on non-OK responses.
 */
async function request(path, token, options = {}) {
  const headers = new Headers(options.headers || {})

  // Attach session token if provided.
  if (token) headers.set('X-Session-Token', token)

  // Auto-set JSON content type for non-FormData request bodies.
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!response.ok) {
    // Parse the error detail from the backend's JSON response.
    const payload = await response.json().catch(() => ({}))
    const detail = payload.detail || ''

    if (response.status === 413) {
      throw new Error(detail || "The PDF file is too large or exceeds the processing limit (max 20 MB / 500 pages).")
    }
    if (response.status === 429) {
      throw new Error(detail || "AI inference capacity is temporarily busy. Please wait a few seconds and try again.")
    }
    if (response.status === 401) {
      throw new Error("Your study session has expired or is invalid. Please start a fresh session.")
    }
    if (response.status >= 500) {
      throw new Error(detail || "The service is temporarily busy processing materials. Please retry in a few moments.")
    }
    throw new Error(detail || `Request failed with status ${response.status}. Please check your connection and retry.`)
  }

  // 204 No Content responses have no body to parse.
  return response.status === 204 ? null : response
}

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

/**
 * Create a new anonymous study session.
 * @returns {Promise<{session_token: string, expires_in: number}>}
 */
export async function createSession() {
  const response = await request('/api/sessions', null, { method: 'POST' })
  return response.json()
}

/**
 * Close the current study session and clean up server-side data.
 * @param {string} token - The session token to close.
 */
export async function closeSession(token) {
  return request('/api/sessions/current', token, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Document operations
// ---------------------------------------------------------------------------

/**
 * Upload a PDF textbook for processing.
 * @param {string} token - Session token.
 * @param {File}   file  - The PDF file to upload.
 * @returns {Promise<object>} Document metadata (ID, page count, etc.).
 */
export async function uploadDocument(token, file) {
  const form = new FormData()
  form.append('file', file)
  const response = await request('/api/documents/upload', token, { method: 'POST', body: form })
  return response.json()
}

/**
 * Fetch metadata for a previously uploaded document.
 * @param {string} token      - Session token.
 * @param {string} documentId - The document's unique ID.
 * @returns {Promise<object>} Document metadata.
 */
export async function getDocument(token, documentId) {
  const response = await request(`/api/documents/${encodeURIComponent(documentId)}`, token)
  return response.json()
}

// ---------------------------------------------------------------------------
// Study material generation and chat
// ---------------------------------------------------------------------------

/**
 * Generate study material or send a chat question.
 * @param {string} path    - API endpoint path (e.g., '/api/study/deep-notes').
 * @param {string} token   - Session token.
 * @param {object} payload - Request body (must include `document_id`).
 * @returns {Promise<object>} The generated material or chat response.
 */
export async function generate(path, token, payload) {
  const response = await request(path, token, { method: 'POST', body: JSON.stringify(payload) })
  return response.json()
}

// ---------------------------------------------------------------------------
// PDF export
// ---------------------------------------------------------------------------

/**
 * Export a generated study material as a downloadable PDF.
 * @param {string} token      - Session token.
 * @param {string} documentId - The document's unique ID.
 * @param {string} kind       - Material type ('deep-notes', 'quiz', etc.).
 * @returns {Promise<Blob>} The PDF file as a binary Blob.
 */
export async function exportPdf(token, documentId, kind) {
  const response = await request('/api/export/pdf', token, {
    method: 'POST',
    body: JSON.stringify({ document_id: documentId, kind }),
  })
  return response.blob()
}


// Centralize the session header and API error contract.