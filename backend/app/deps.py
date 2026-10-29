import uuid
from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.engine import get_db
from app.db.models import User, AuthSession
from app.auth.jwt import decode_access_token
from app.auth.cookies import ACCESS_COOKIE_NAME

async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Retrieves authenticated user from vexovault_at cookie if valid, otherwise None."""
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        # Also check Authorization header Bearer token for API/test convenience
        auth_hdr = request.headers.get("Authorization")
        if auth_hdr and auth_hdr.startswith("Bearer "):
            token = auth_hdr.split(" ")[1]

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        return None

    try:
        u_uuid = uuid.UUID(user_id)
        s_uuid = uuid.UUID(session_id)
    except ValueError:
        return None

    # Verify session is not revoked
    stmt = select(AuthSession).where(
        AuthSession.id == s_uuid,
        AuthSession.user_id == u_uuid,
        AuthSession.revoked_at.is_(None)
    )
    result = await db.execute(stmt)
    session_row = result.scalar_one_or_none()
    if not session_row:
        return None

    # Load active user
    u_stmt = select(User).where(User.id == u_uuid, User.deleted_at.is_(None))
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    return user

async def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """Strict dependency requiring authenticated user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided or have expired"
        )
    return user
