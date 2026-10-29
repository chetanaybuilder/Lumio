import hmac
from fastapi import Request, HTTPException, status
from app.auth.cookies import CSRF_COOKIE_NAME

async def verify_csrf(request: Request):
    """
    Verifies CSRF token for state-changing HTTP methods.
    Compares the X-CSRF-Token header with the vexovault_csrf cookie using constant-time comparison.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # In test mode, allow skipping if header is explicitly test bypass
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("X-CSRF-Token")

    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from cookie or header"
        )

    if not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch"
        )
