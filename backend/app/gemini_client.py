"""
Compatibility shim forwarding to Groq client.
Gemini has been completely replaced with Groq for all AI inference.
"""

from app.groq_client import (
    EMBEDDING_DIMENSIONS,
    embed_texts,
    generate_structured,
    get_client,
)

__all__ = ["EMBEDDING_DIMENSIONS", "embed_texts", "generate_structured", "get_client"]