import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.config import settings
from app.db.engine import get_db
from app.db.models import User, AuthSession
from app.deps import get_current_user
from app.auth.google import verify_google_credential
from app.auth.jwt import (
    create_access_token,
    generate_refresh_token,
    generate_csrf_token,
    hash_token
)
from app.auth.cookies import (
    set_auth_cookies,
    clear_auth_cookies,
    REFRESH_COOKIE_NAME,
    ACCESS_COOKIE_NAME
)
from app.auth.csrf import verify_csrf
import ipaddress

def safe_ip(ip_str: Optional[str]) -> Optional[str]:
    if not ip_str:
        return None
    try:
        ipaddress.ip_address(ip_str)
        return ip_str
    except ValueError:
        return None

router = APIRouter(prefix="/auth", tags=["auth"])
test_router = APIRouter(prefix="/test", tags=["test_only"])

class GoogleLoginRequest(BaseModel):
    credential: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    class_level: Optional[int]
    board: str

@router.post("/google", response_model=UserResponse)
async def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    google_data = verify_google_credential(payload.credential)
    if not google_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token"
        )

    sub = google_data["sub"]
    email = google_data["email"]
    name = google_data.get("name")
    picture = google_data.get("picture")

    # Upsert user by google_sub
    stmt = select(User).where(User.google_sub == sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not user:
        # Check if user with same email exists
        email_stmt = select(User).where(User.email == email)
        email_res = await db.execute(email_stmt)
        user = email_res.scalar_one_or_none()
        if user:
            user.google_sub = sub
            user.email_verified = True
            user.full_name = name or user.full_name
            user.avatar_url = picture or user.avatar_url
            user.last_login_at = now
        else:
            user = User(
                id=uuid.uuid4(),
                google_sub=sub,
                email=email,
                email_verified=True,
                full_name=name,
                avatar_url=picture,
                class_level=12,
                board="CBSE",
                created_at=now,
                updated_at=now,
                last_login_at=now
            )
            db.add(user)
    else:
        user.last_login_at = now
        if name:
            user.full_name = name
        if picture:
            user.avatar_url = picture

    await db.flush()

    # Create new session family
    family_id = uuid.uuid4()
    session_id = uuid.uuid4()
    refresh_token = generate_refresh_token()
    rf_hash = hash_token(refresh_token)

    auth_sess = AuthSession(
        id=session_id,
        user_id=user.id,
        family_id=family_id,
        refresh_token_hash=rf_hash,
        user_agent=request.headers.get("user-agent"),
        ip=safe_ip(request.client.host) if request.client else None,
        created_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(auth_sess)
    await db.commit()

    # Issue tokens & cookies
    access_token = create_access_token(str(user.id), str(session_id))
    csrf_token = generate_csrf_token()
    set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        class_level=user.class_level,
        board=user.board
    )

@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    rf_hash = hash_token(refresh_token)
    stmt = select(AuthSession).where(AuthSession.refresh_token_hash == rf_hash)
    result = await db.execute(stmt)
    session_row = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not session_row:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Check theft signal: if presented token is already revoked, revoke whole family!
    if session_row.revoked_at is not None:
        revoke_family_stmt = update(AuthSession).where(
            AuthSession.family_id == session_row.family_id
        ).values(revoked_at=now)
        await db.execute(revoke_family_stmt)
        await db.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked due to reuse signal"
        )

    # Check expiration
    exp_time = session_row.expires_at
    if exp_time.tzinfo is None:
        exp_time = exp_time.replace(tzinfo=timezone.utc)
    if exp_time <= now:
        session_row.revoked_at = now
        await db.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )

    # Rotate session
    new_session_id = uuid.uuid4()
    new_refresh_token = generate_refresh_token()
    new_rf_hash = hash_token(new_refresh_token)

    new_auth_sess = AuthSession(
        id=new_session_id,
        user_id=session_row.user_id,
        family_id=session_row.family_id,
        refresh_token_hash=new_rf_hash,
        user_agent=request.headers.get("user-agent"),
        ip=safe_ip(request.client.host) if request.client else None,
        created_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_auth_sess)
    await db.flush()

    session_row.revoked_at = now
    session_row.replaced_by = new_session_id
    await db.commit()

    access_token = create_access_token(str(session_row.user_id), str(new_session_id))
    csrf_token = generate_csrf_token()
    set_auth_cookies(response, access_token, new_refresh_token, csrf_token)

    return {"status": "refreshed"}

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        rf_hash = hash_token(refresh_token)
        now = datetime.now(timezone.utc)
        await db.execute(
            update(AuthSession).where(AuthSession.refresh_token_hash == rf_hash).values(revoked_at=now)
        )
        await db.commit()

    clear_auth_cookies(response)
    return {"status": "logged_out"}

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        class_level=user.class_level,
        board=user.board
    )

# Test-Only Login (Registered only in non-production environments)
@test_router.post("/login", response_model=UserResponse)
async def test_login(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Mints authentication cookies for a seeded test user."""
    test_email = "student@vexovault.test"
    stmt = select(User).where(User.email == test_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not user:
        user = User(
            id=uuid.uuid4(),
            google_sub="test-google-sub-vexovault-001",
            email=test_email,
            email_verified=True,
            full_name="VexoVault Test Student",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=vexovault",
            class_level=12,
            board="CBSE",
            created_at=now,
            updated_at=now,
            last_login_at=now
        )
        db.add(user)
        await db.flush()

    family_id = uuid.uuid4()
    session_id = uuid.uuid4()
    refresh_token = generate_refresh_token()
    rf_hash = hash_token(refresh_token)

    auth_sess = AuthSession(
        id=session_id,
        user_id=user.id,
        family_id=family_id,
        refresh_token_hash=rf_hash,
        user_agent="VexoVault-Test-Client",
        ip="127.0.0.1",
        created_at=now,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(auth_sess)
    await db.commit()

    access_token = create_access_token(str(user.id), str(session_id))
    csrf_token = generate_csrf_token()
    set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        class_level=user.class_level,
        board=user.board
    )
