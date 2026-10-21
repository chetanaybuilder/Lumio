"""
Session Manager — Lumio Backend
=================================

Provides an in-memory session registry that associates each browser tab
with a private, time-limited study workspace.

Key design decisions:

- **Token generation** uses ``secrets.token_urlsafe(32)`` for
  cryptographic randomness.
- **Sliding TTL** — every successful ``get_session`` call resets the
  expiry clock, so active users are never interrupted.
- **Async lock** — a single ``asyncio.Lock`` serializes mutations to
  prevent race conditions in concurrent request handlers.
- **Process-local storage** — sessions live only in the current process
  and do not survive restarts.  This is intentional for the MVP: there
  are no accounts, no persistent user data, and no cross-worker sharing.

The cleanup loop in ``main.py`` periodically calls ``expired_sessions``
and removes stale entries along with their vector-store data.
"""

import asyncio
import secrets
import time
from dataclasses import dataclass, field

from app.config import SESSION_TTL_SECONDS


# ---------------------------------------------------------------------------
# Session data model
# ---------------------------------------------------------------------------

@dataclass
class StudySession:
    """
    Represents one browser tab's private study workspace.

    Attributes
    ----------
    token : str
        Opaque session identifier sent as ``X-Session-Token``.
    expires_at : float
        Unix timestamp after which the session is considered expired.
    documents : dict[str, dict]
        Uploaded documents keyed by document ID.  Each value contains
        filename, page count, sections, chunks, and cached materials.
    chat : dict[str, list[dict]]
        Per-document chat history (most recent turns only).
    """
    token: str
    expires_at: float
    documents: dict[str, dict] = field(default_factory=dict)
    chat: dict[str, list[dict]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory registry
# ---------------------------------------------------------------------------

# Global session store — keyed by token string.
sessions: dict[str, StudySession] = {}

# Async lock protecting all mutations to the ``sessions`` dictionary.
session_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

async def create_session() -> StudySession:
    """
    Create a new study session with a cryptographically random token.

    Returns
    -------
    StudySession
        The newly created session, already registered in the global store.
    """
    token = secrets.token_urlsafe(32)
    session = StudySession(token, time.time() + SESSION_TTL_SECONDS)
    async with session_lock:
        sessions[token] = session
    return session


async def get_session(token: str | None) -> StudySession | None:
    """
    Look up and refresh a session by its token.

    If the session exists and has not expired, its ``expires_at`` is
    extended by another ``SESSION_TTL_SECONDS`` (sliding window).

    Parameters
    ----------
    token : str or None
        The ``X-Session-Token`` header value.

    Returns
    -------
    StudySession or None
        The active session, or ``None`` if the token is missing, unknown,
        or expired.
    """
    if not token:
        return None
    async with session_lock:
        session = sessions.get(token)
        if session and session.expires_at > time.time():
            # Sliding expiry — reset the clock on every valid access.
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            return session
        return None


async def remove_session(token: str) -> StudySession | None:
    """
    Remove a session from the registry.

    Returns
    -------
    StudySession or None
        The removed session, or ``None`` if the token was not found.
    """
    async with session_lock:
        return sessions.pop(token, None)


async def expired_sessions() -> list[StudySession]:
    """
    Return a snapshot of all sessions whose TTL has elapsed.

    The caller is responsible for cleaning up vector-store data and then
    calling ``remove_session`` for each expired entry.
    """
    now = time.time()
    async with session_lock:
        return [item for item in sessions.values() if item.expires_at <= now]


# Tokens and cached material exist only for the active process lifetime.