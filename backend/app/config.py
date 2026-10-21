"""
Configuration Module — Lumio Backend
=====================================

Centralizes every environment-driven setting the backend reads at startup.
Values fall back to sensible development defaults so the application can
start without a `.env` file for local testing, while production deployments
override them through process environment variables.

Environment variables
---------------------
GROQ_API_KEY           : API key for Groq Cloud (high-speed LLM inference).
GROQ_MODEL             : Text-generation model name (default: openai/gpt-oss-20b).
LUMIO_TEMP_DIR         : Writable directory for temporary upload files.
LUMIO_CHROMA_DIR       : Persistent directory for the ChromaDB vector store.
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

# Persistent storage path for the ChromaDB vector database.
CHROMA_DIR = Path(os.getenv("LUMIO_CHROMA_DIR", BASE_DIR / ".chroma"))


# ---------------------------------------------------------------------------
# Groq AI provider
# ---------------------------------------------------------------------------

# Groq API key — required for high-speed study-material generation and chat.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Text-generation model identifier used for notes, quizzes, flashcards, and chat.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


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