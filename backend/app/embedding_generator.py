"""
Embedding Generator — Lumio Backend
=====================================

Thin convenience layer over ``gemini_client.embed_texts`` that adds:

- Input validation (type checks and empty-string rejection).
- Automatic batching — large document chunk lists are split into batches
  of ``BATCH_SIZE`` texts to stay within provider request-size limits.
- A single-text shortcut (``generate_embedding``) for query-time use.

Two Gemini task types control how vectors are optimized:

- ``RETRIEVAL_DOCUMENT`` — used when embedding stored document chunks.
- ``RETRIEVAL_QUERY`` — used when embedding a student's question for
  nearest-neighbor search against stored chunks.
"""

from app.groq_client import EMBEDDING_DIMENSIONS, embed_texts

__all__ = ["EMBEDDING_DIMENSIONS", "generate_embedding", "generate_embeddings_batch", "BATCH_SIZE"]

# ---------------------------------------------------------------------------
# Provider batch-size limit
# ---------------------------------------------------------------------------

# Maximum number of texts sent to Gemini in a single embedding request.
BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Single-text embedding
# ---------------------------------------------------------------------------

def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate an embedding vector for one text string.

    Parameters
    ----------
    text : str
        The text to embed.  Must be a non-empty string.
    task_type : str, optional
        Gemini task type (default ``RETRIEVAL_DOCUMENT``).

    Returns
    -------
    list[float]
        A 768-dimensional embedding vector.

    Raises
    ------
    TypeError
        If *text* is not a string.
    ValueError
        If *text* is empty or whitespace-only.
    RuntimeError
        If the Gemini provider call fails.
    """
    if not isinstance(text, str):
        raise TypeError("Text must be a string")

    if not text.strip():
        raise ValueError("Text cannot be empty")

    try:
        return embed_texts([text], task_type)[0]
    except Exception as error:
        raise RuntimeError("Failed to generate embedding.") from error


# ---------------------------------------------------------------------------
# Batch embedding
# ---------------------------------------------------------------------------

def generate_embeddings(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Generate embedding vectors for multiple texts, batching automatically.

    Parameters
    ----------
    texts : list[str]
        A list of non-empty text strings to embed.
    task_type : str, optional
        Task type (default ``RETRIEVAL_DOCUMENT``).

    Returns
    -------
    list[list[float]]
        One vector per input text.

    Raises
    ------
    TypeError
        If *texts* is not a list or contains non-string items.
    ValueError
        If any text in the list is empty or whitespace-only.
    RuntimeError
        If embedding generation fails.
    """
    if not isinstance(texts, list):
        raise TypeError("Texts must be provided as a list")

    if not texts:
        return []

    # Validate every item before sending anything to the provider.
    for text in texts:
        if not isinstance(text, str):
            raise TypeError("Every item in texts must be a string")
        if not text.strip():
            raise ValueError("Texts cannot contain empty strings")

    try:
        # Split the request into batches to respect size limits.
        embeddings = []
        for start in range(0, len(texts), BATCH_SIZE):
            embeddings.extend(embed_texts(texts[start:start + BATCH_SIZE], task_type))
        return embeddings
    except Exception as error:
        raise RuntimeError("Failed to generate embeddings.") from error


# Document and query vectors share model dimensions but use distinct task types.