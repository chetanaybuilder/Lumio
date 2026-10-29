import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Dict, List
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from app.config import settings
from app.db.engine import init_db
from app.logging import setup_structured_logging, RequestIdMiddleware
from app.errors import (
    http_exception_handler,
    ai_output_error_handler,
    generic_exception_handler,
    AIOutputError
)

from app.auth.router import router as auth_router, test_router
from app.uploads.router import router as uploads_router
from app.features.notes import router as notes_router
from app.features.flashcards import router as flashcards_router
from app.features.cheatsheet import router as cheatsheet_router
from app.features.tutor import router as tutor_router
from app.features.paper import router as paper_router
from app.features.evaluate import router as evaluate_router
from app.features.mistakes import router as mistakes_router
from app.features.coverage import router as coverage_router
from app.features.roadmap import router as roadmap_router

# Setup structured logging
setup_structured_logging()

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' accounts.google.com; "
            "script-src 'self' 'unsafe-inline' accounts.google.com; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' accounts.google.com;"
        )
        return response

# Rate Limiter Middleware for Auth routes (10 req/min per IP)
class AuthRateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.ip_hits: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/auth/"):
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            # Retain only hits in last 60 seconds
            self.ip_hits[client_ip] = [t for t in self.ip_hits[client_ip] if now - t < 60]
            if len(self.ip_hits[client_ip]) >= 10:
                return JSONResponse(
                    status_code=429,
                    content={"error": "RATE_LIMIT_EXCEEDED", "detail": "Too many auth requests. Please wait a minute."}
                )
            self.ip_hits[client_ip].append(now)

        return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Invariant 12: Test-only code cannot reach production.
    # The server refuses to start if ENV=production and any route tagged test_only is registered.
    if settings.ENV == "production":
        for route in app.routes:
            if hasattr(route, "tags") and "test_only" in (route.tags or []):
                raise RuntimeError("CRITICAL SECURITY VIOLATION: Route tagged 'test_only' is registered in production!")

    # Initialize tables
    try:
        await init_db()
    except Exception as e:
        import logging
        logging.getLogger("vexovault").warning(f"Database init warning (expected if migrations manage schema): {e}")

    yield

app = FastAPI(
    title="VexoVault API",
    version="2.0.0",
    description="VexoVault — Architecture & Implementation Backend",
    lifespan=lifespan
)

# Add Middlewares
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthRateLimiterMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(AIOutputError, ai_output_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Health Check
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "version": "2.0.0"
    }

# Register Routers
app.include_router(auth_router)
if settings.ENV != "production":
    app.include_router(test_router)

app.include_router(uploads_router, prefix="/api")
app.include_router(notes_router, prefix="/api")
app.include_router(flashcards_router, prefix="/api")
app.include_router(cheatsheet_router, prefix="/api")
app.include_router(tutor_router, prefix="/api")
app.include_router(paper_router, prefix="/api")
app.include_router(evaluate_router, prefix="/api")
app.include_router(mistakes_router, prefix="/api")
app.include_router(coverage_router, prefix="/api")
app.include_router(roadmap_router, prefix="/api")
