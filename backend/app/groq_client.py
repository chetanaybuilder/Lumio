"""
Groq Client (Deprecated) — Lumio Backend
========================================

Forwarding shim to `app.cloudflare_client` for backward compatibility.
All LLM generation in Lumio is powered by Cloudflare Workers AI.
"""

from app.cloudflare_client import (
    EMBEDDING_DIMENSIONS,
    _sanitize_json,
    generate_structured,
)

__all__ = ["generate_structured", "_sanitize_json", "EMBEDDING_DIMENSIONS"]
