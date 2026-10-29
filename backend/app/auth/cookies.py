from fastapi import Response
from app.config import settings

ACCESS_COOKIE_NAME = "vexovault_at"
REFRESH_COOKIE_NAME = "vexovault_rt"
CSRF_COOKIE_NAME = "vexovault_csrf"

def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str
):
    """Sets the three security cookies for VexoVault authentication."""
    # 1. Access Token: HttpOnly, 15 minutes, Path /
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/"
    )
    
    # 2. Refresh Token: HttpOnly, 30 days, Path /auth
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/auth"
    )
    
    # 3. CSRF Token: JavaScript-readable (not HttpOnly), Path /
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/"
    )

def clear_auth_cookies(response: Response):
    """Clears all three security cookies on logout."""
    response.delete_cookie(
        key=ACCESS_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/"
    )
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/auth"
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        domain=settings.COOKIE_DOMAIN,
        path="/"
    )
