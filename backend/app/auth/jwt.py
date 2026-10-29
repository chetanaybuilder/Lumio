import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
from app.config import settings

def hash_token(token: str) -> str:
    """Computes SHA-256 hex digest of an opaque token."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def create_access_token(user_id: str, session_id: str) -> str:
    """
    Creates HS256 access JWT valid for 15 minutes.
    Claims: sub (user UUID), sid (session ID), iat, exp, iss='vexovault', aud='vexovault-api'.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates access token claims."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None

def generate_refresh_token() -> str:
    """Generates opaque 256-bit random URL-safe refresh token."""
    return secrets.token_urlsafe(32)

def generate_csrf_token() -> str:
    """Generates random CSRF token."""
    return secrets.token_hex(24)
