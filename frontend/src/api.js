const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function request(path, token, options = {}) {
  const headers = new Headers(options.headers || {})
  if (token) headers.set('X-Session-Token', token)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Request failed (${response.status})`)
  }
  return response.status === 204 ? null : response
}

export async function createSession() {
  const response = await request('/api/sessions', null, { method: 'POST' })
  return response.json()
}

export async function uploadDocument(token, file) {
  const form = new FormData()
  form.append('file', file)
  const response = await request('/api/documents/upload', token, { method: 'POST', body: form })
  return response.json()
}

export async function getDocument(token, documentId) {
  const response = await request(`/api/documents/${encodeURIComponent(documentId)}`, token)
  return response.json()
}

export async function generate(token, path, payload) {
  const response = await request(path, token, { method: 'POST', body: JSON.stringify(payload) })
  return response.json()
}

export async function exportPdf(token, documentId, kind) {
  const response = await request('/api/export/pdf', token, {
    method: 'POST',
    body: JSON.stringify({ document_id: documentId, kind }),
  })
  return response.blob()
}

export async function closeSession(token) {
  return request('/api/sessions/current', token, { method: 'DELETE' })
}


// Centralize the session header and API error contract.