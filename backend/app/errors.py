from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from app.ai.client import AIOutputError

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    retry_hint: Optional[str] = None

async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

async def ai_output_error_handler(request: Request, exc: AIOutputError):
    return JSONResponse(
        status_code=502,
        content={
            "error": "AI_OUTPUT_VALIDATION_FAILED",
            "detail": exc.message,
            "retry_hint": exc.retry_hint
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_SERVER_ERROR", "detail": str(exc)}
    )
