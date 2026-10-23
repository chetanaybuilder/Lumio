"""
Configuration Module — Lumio Backend
=====================================

Centralizes every environment-driven setting the backend reads at startup.
Values fall back to sensible development defaults so the application can
start without a `.env` file for local testing, while production deployments
override them through process environment variables.

Environment variables
---------------------
CLOUDFLARE_ACCOUNT_ID  : Account ID for Cloudflare Workers AI.
CLOUDFLARE_API_TOKEN   : API token for Cloudflare Workers AI inference.
CLOUDFLARE_MODEL       : Primary text-generation model (default: @cf/meta/llama-3.3-70b-instruct-fp8-fast).
CLOUDFLARE_FALLBACK_MODEL : Fallback text-generation model (default: @cf/meta/llama-3.1-8b-instruct-fp8).
LUMIO_TEMP_DIR         : Writable directory for temporary upload files.
SESSION_TTL_SECONDS    : Sliding inactivity expiry for study sessions (seconds).
MAX_UPLOAD_MB          : Maximum PDF upload size in megabytes.
MAX_PDF_PAGES          : Maximum number of pages allowed in a single PDF.
FRONTEND_ORIGINS       : Comma-separated list of allowed CORS origins.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

# The backend package root (one level above `app/`).
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# Temporary directory for streamed PDF uploads before processing.
TEMP_DIR = Path(os.getenv("LUMIO_TEMP_DIR", BASE_DIR / "temp"))


# ---------------------------------------------------------------------------
# Cloudflare Workers AI provider
# ---------------------------------------------------------------------------

# Cloudflare Account ID — found in your Cloudflare dashboard overview.
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "8b2dd8293e95e2a90c65bb8a7fb91632")

# Cloudflare API Token — created with Workers AI read/write permissions.
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")

# Text-generation model identifier used for notes, quizzes, flashcards, and chat.
CLOUDFLARE_MODEL = os.getenv("CLOUDFLARE_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")

# Fast fallback model when primary model is busy or hits rate limits.
CLOUDFLARE_FALLBACK_MODEL = os.getenv("CLOUDFLARE_FALLBACK_MODEL", "@cf/meta/llama-3.1-8b-instruct-fp8")


# ---------------------------------------------------------------------------
# Session and upload limits
# ---------------------------------------------------------------------------

# How long (in seconds) an idle session survives before automatic cleanup.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))

# Maximum upload size in bytes (derived from the MB environment variable).
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024

# Maximum number of pages the PDF extractor will accept.
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "500"))


# ---------------------------------------------------------------------------
# CORS — allowed frontend origins
# ---------------------------------------------------------------------------

# Comma-separated origins that may call the API (used by the CORS middleware).
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


# Keep deployment-specific limits and paths in one place.