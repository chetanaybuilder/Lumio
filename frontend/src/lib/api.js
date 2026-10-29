import { ZodError } from 'zod';

let isRefreshing = false;
let refreshPromise = null;

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match ? decodeURIComponent(match[3]) : null;
}

export async function request(path, options = {}, schema = null) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});

  // Add credentials include
  const fetchOpts = {
    ...options,
    method,
    headers,
    credentials: 'include'
  };

  // Add X-CSRF-Token on unsafe methods
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCookie('vexovault_csrf');
    if (csrfToken && !headers.has('X-CSRF-Token')) {
      headers.set('X-CSRF-Token', csrfToken);
    }
    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }
  }

  let response = await fetch(path, fetchOpts);

  // If 401 Unauthorized, perform single in-flight refresh then retry once
  if (response.status === 401 && !path.includes('/auth/refresh') && !path.includes('/auth/google')) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = fetch('/auth/refresh', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'X-CSRF-Token': getCookie('vexovault_csrf') || ''
        }
      }).then(res => {
        isRefreshing = false;
        return res.ok;
      }).catch(() => {
        isRefreshing = false;
        return false;
      });
    }

    const refreshSuccess = await refreshPromise;
    if (refreshSuccess) {
      // Re-fetch with new cookie
      const newCsrf = getCookie('vexovault_csrf');
      if (newCsrf && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        headers.set('X-CSRF-Token', newCsrf);
      }
      response = await fetch(path, fetchOpts);
    }
  }

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.error || errorDetail;
    } catch (_) {}
    throw new Error(errorDetail);
  }

  if (response.status === 204) {
    return null;
  }

  const data = await response.json();

  // Runtime schema validation with Zod
  if (schema) {
    try {
      return schema.parse(data);
    } catch (err) {
      if (err instanceof ZodError) {
        console.error(`[API Schema Mismatch at ${path}]:`, err.errors);
        throw new Error(`API Contract Violation on ${path}: ${err.errors.map(e => e.message).join(', ')}`);
      }
      throw err;
    }
  }

  return data;
}

// Convenient API methods
export const api = {
  request,

  // Auth
  getCurrentUser: () => request('/auth/me'),
  loginTest: (email) => request('/test/login', { method: 'POST', body: JSON.stringify({ email }) }),
  logout: () => request('/auth/logout', { method: 'POST' }),

  // Documents & Vault
  getDocuments: async () => {
    const vault = await request('/api/vault');
    return vault.documents || [];
  },
  getDocument: (id) => request(`/api/documents/${id}`),
  getDocumentStatus: (id) => request(`/api/documents/${id}/status`),

  // Notes & Flashcards
  getNote: (id) => request(`/api/notes/${id}`),
  generateNotes: (docId) => request(`/api/documents/${docId}/notes`, { method: 'POST' }),
  getDueFlashcards: () => request('/api/flashcards/due'),
  reviewFlashcard: (cardId, quality) =>
    request(`/api/flashcards/${cardId}/review`, {
      method: 'POST',
      body: JSON.stringify({ quality })
    }),
  createFlashcardsFromNote: (noteId) =>
    request(`/api/notes/${noteId}/flashcards`, { method: 'POST' }),

  // Cheat Sheet
  getCheatSheet: (docId) => request(`/api/documents/${docId}/cheatsheet`, { method: 'POST' }),

  // Socratic Tutor
  createTutorSession: (data) =>
    request('/api/tutor/sessions', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  streamTutorMessage: async (sessionId, message, hintLevel, onToken, onDone, onError) => {
    try {
      const csrfToken = getCookie('vexovault_csrf');
      const response = await fetch(`/api/tutor/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        },
        credentials: 'include',
        body: JSON.stringify({
          message,
          hint_level: hintLevel
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;
            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.event === 'token' || parsed.token) {
                onToken(parsed.token || parsed.content || '');
              } else if (parsed.event === 'done' || parsed.status === 'done') {
                onDone(parsed);
              } else if (parsed.event === 'error') {
                onError(parsed.error || 'Tutor stream error');
              }
            } catch (_) {
              // Plain text token fallback
              onToken(dataStr);
            }
          }
        }
      }
      onDone({});
    } catch (err) {
      onError(err.message || 'Stream connection failed');
    }
  },

  // CBSE Paper Generator
  getQuizzes: () => request('/api/quizzes'),
  getQuiz: (id) => request(`/api/quizzes/${id}`),
  createQuiz: (payload) =>
    request('/api/quizzes', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  createQuizAttempt: (quizId) =>
    request(`/api/quizzes/${quizId}/attempts`, {
      method: 'POST'
    }),
  submitQuizAttempt: (attemptId, payload) =>
    request(`/api/attempts/${attemptId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),

  // Marks Improvement AI Evaluation
  evaluateAnswer: (payload) =>
    request('/api/evaluate', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),

  // Mistake Tracker & Drills
  getMistakes: () => request('/api/mistakes'),
  createMistakeDrill: (mistakeId) =>
    request(`/api/mistakes/${mistakeId}/drill`, {
      method: 'POST'
    }),

  // Revision Roadmap
  getRoadmap: (date) => request(`/api/roadmap${date ? `?date=${date}` : ''}`),
  createExamTarget: (payload) =>
    request('/api/exam-targets', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
};

export default api;
