import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
TEMP_DIR = Path(os.getenv("LUMIO_TEMP_DIR", BASE_DIR / "temp"))
CHROMA_DIR = Path(os.getenv("LUMIO_CHROMA_DIR", BASE_DIR / ".chroma"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "500"))
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


# Keep deployment-specific limits and paths in one place.