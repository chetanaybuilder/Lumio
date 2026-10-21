"""
Gemini Client — Lumio Backend
==============================

Provides a single, shared Google Gemini client that the rest of the
application uses for two distinct capabilities:

1. **Embeddings** — converting text into 768-dimensional vectors via the
   ``gemini-embedding-001`` model for storage and retrieval in ChromaDB.
2. **Structured generation** — prompting a text-generation model (default
   ``gemini-3.8-flash``) and validating the JSON response against a
   Pydantic schema so that every generated artifact (notes, quiz,
   flashcards, chat answer) is type-safe before it reaches the API layer.

The client is instantiated lazily and cached for the process lifetime.
All provider-level errors surface as ``RuntimeError`` with a safe message
so that internal API keys or endpoint details are never exposed to callers.
"""

import json
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import GEMINI_API_KEY, GEMINI_MODEL


# ---------------------------------------------------------------------------
# Type variable for generic structured-output validation
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Embedding model constants
# ---------------------------------------------------------------------------

# The embedding model name and output vector size used globally.
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_client():
    """
    Return a cached Gemini client instance.

    Raises ``RuntimeError`` if the API key has not been configured,
    preventing the application from silently sending unauthenticated
    requests.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY and restart the API.")
    return genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 120000})


# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """
    Generate embedding vectors for a batch of texts.

    Parameters
    ----------
    texts : list[str]
        The text strings to embed.
    task_type : str
        Gemini task type — ``RETRIEVAL_DOCUMENT`` for stored chunks,
        ``RETRIEVAL_QUERY`` for user questions.

    Returns
    -------
    list[list[float]]
        One 768-dimensional vector per input text.

    Raises
    ------
    RuntimeError
        If the response contains the wrong number of vectors or any
        vector has an unexpected dimensionality.
    """
    if not texts:
        return []

    import time
    last_err = None
    for attempt in range(4):
        try:
            response = get_client().models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBEDDING_DIMENSIONS,
                ),
            )
            vectors = [list(item.values or []) for item in response.embeddings or []]
            if len(vectors) != len(texts) or any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
                raise RuntimeError("Gemini returned an invalid embedding response.")
            return vectors
        except Exception as exc:
            last_err = exc
            if attempt < 3 and any(code in str(exc) for code in ("503", "504", "429", "UNAVAILABLE", "DEADLINE_EXCEEDED")):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini embedding error: {exc}") from exc
    raise RuntimeError(f"Gemini embedding failed after retries: {last_err}")


# ---------------------------------------------------------------------------
# Structured text generation
# ---------------------------------------------------------------------------

def generate_structured(prompt: str, output_type: type[T]) -> T:
    """
    Prompt Gemini for a JSON response and validate it against *output_type*.

    The model is instructed to return ``application/json`` conforming to the
    Pydantic schema.  If the SDK provides a pre-parsed object we validate
    it; otherwise we fall back to parsing the raw text.

    Parameters
    ----------
    prompt : str
        The full prompt string (already assembled by ``prompt_templates``).
    output_type : type[T]
        A Pydantic ``BaseModel`` subclass to validate the response against.

    Returns
    -------
    T
        A validated instance of *output_type*.

    Raises
    ------
    RuntimeError
        If validation fails or the response is empty / malformed.
    """
    import time
    last_err = None
    for attempt in range(4):
        try:
            response = get_client().models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=output_type,
                    temperature=0.2,
                ),
            )
            try:
                if response.parsed is not None:
                    return output_type.model_validate(response.parsed)
                return output_type.model_validate(json.loads(response.text or ""))
            except (ValidationError, ValueError, TypeError) as error:
                raise RuntimeError("Gemini returned incomplete or invalid study content.") from error
        except Exception as exc:
            last_err = exc
            if attempt < 3 and any(code in str(exc) for code in ("503", "504", "429", "UNAVAILABLE", "DEADLINE_EXCEEDED")):
                time.sleep(2.0 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini generation error: {exc}") from exc
    raise RuntimeError(f"Gemini generation failed after retries: {last_err}")


# Keep Gemini configuration and failure handling centralized.