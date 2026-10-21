import asyncio
import secrets
import time
from dataclasses import dataclass, field

from app.config import SESSION_TTL_SECONDS


@dataclass
class StudySession:
    token: str
    expires_at: float
    documents: dict[str, dict] = field(default_factory=dict)
    chat: dict[str, list[dict]] = field(default_factory=dict)


sessions: dict[str, StudySession] = {}
session_lock = asyncio.Lock()


async def create_session() -> StudySession:
    token = secrets.token_urlsafe(32)
    session = StudySession(token, time.time() + SESSION_TTL_SECONDS)
    async with session_lock:
        sessions[token] = session
    return session


async def get_session(token: str | None) -> StudySession | None:
    if not token:
        return None
    async with session_lock:
        session = sessions.get(token)
        if session and session.expires_at > time.time():
            session.expires_at = time.time() + SESSION_TTL_SECONDS
            return session
        return None


async def remove_session(token: str) -> StudySession | None:
    async with session_lock:
        return sessions.pop(token, None)


async def expired_sessions() -> list[StudySession]:
    now = time.time()
    async with session_lock:
        return [item for item in sessions.values() if item.expires_at <= now]


# Tokens and cached material exist only for the active process lifetime.