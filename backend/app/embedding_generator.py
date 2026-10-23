"""
Embedding Generator — Lumio Backend
=====================================

Provides high-speed, local semantic embeddings using ONNX Runtime
(BAAI/bge-small-en-v1.5) with normalized 384-dimensional dense vectors:

- Automatic batching and thread-safe singleton model management.
- L2 normalization for exact cosine similarity dot products.
- Robust deterministic fallback if local model cache is initializing.
- Query embedding shortcut with in-memory caching.
"""

import hashlib
import logging
import math
import re
import threading
from functools import lru_cache

logger = logging.getLogger("lumio.embeddings")

EMBEDDING_DIMENSIONS = 384
BATCH_SIZE = 64

__all__ = ["EMBEDDING_DIMENSIONS", "generate_embedding", "generate_embeddings", "BATCH_SIZE"]

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Lazily load and cache the BAAI/bge-small-en-v1.5 ONNX embedding model."""
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            try:
                from fastembed import TextEmbedding
                logger.info("Initializing local ONNX embedding model: BAAI/bge-small-en-v1.5")
                _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            except Exception as exc:
                logger.warning("Could not initialize FastEmbed model (%s); using normalized fallback: %s", type(exc).__name__, exc)
                _model = False
    return _model


def _fallback_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Microsecond normalized fallback vectorizer when ONNX engine is unavailable."""
    words = re.findall(r"\w+", text.lower())
    if not words:
        return [0.0] * dimensions

    vec = [0.0] * dimensions
    # 1. Unigrams
    for word in words:
        slot = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16) % dimensions
        vec[slot] += 1.0

    # 2. Bigrams
    for i in range(len(words) - 1):
        bigram = f"{words[i]}_{words[i+1]}"
        slot = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest()[:8], 16) % dimensions
        vec[slot] += 1.5

    # 3. Trigrams
    for i in range(len(words) - 2):
        trigram = f"{words[i]}_{words[i+1]}_{words[i+2]}"
        slot = int(hashlib.sha1(trigram.encode("utf-8")).hexdigest()[:8], 16) % dimensions
        vec[slot] += 2.0

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        vec = [x / norm for x in vec]
    return vec


# ---------------------------------------------------------------------------
# Single-text embedding with query caching
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1024)
def _cached_query_embedding(text: str) -> tuple[float, ...]:
    """Cache query embeddings in memory for rapid repeated questions."""
    vec = generate_embeddings([text])[0]
    return tuple(vec)


def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate an embedding vector for one text string.

    Parameters
    ----------
    text : str
        The text to embed. Must be a non-empty string.
    task_type : str, optional
        Task type indicator.

    Returns
    -------
    list[float]
        A 384-dimensional normalized embedding vector.
    """
    if not isinstance(text, str):
        raise TypeError("Text must be a string")

    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Text cannot be empty")

    if task_type == "RETRIEVAL_QUERY":
        return list(_cached_query_embedding(cleaned))

    return generate_embeddings([cleaned])[0]


# ---------------------------------------------------------------------------
# Batch embedding
# ---------------------------------------------------------------------------

def generate_embeddings(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Generate embedding vectors for multiple texts with batching.

    Parameters
    ----------
    texts : list[str]
        A list of non-empty text strings to embed.
    task_type : str, optional
        Task type indicator.

    Returns
    -------
    list[list[float]]
        One 384-dimensional normalized vector per input text.
    """
    if not isinstance(texts, list):
        raise TypeError("texts must be a list of strings")

    for idx, t in enumerate(texts):
        if not isinstance(t, str):
            raise TypeError(f"Item {idx} is not a string")
        if not t.strip():
            raise ValueError(f"Item {idx} is empty or whitespace-only")

    if not texts:
        return []

    model = _get_model()
    if model:
        try:
            # FastEmbed embed generator
            results = []
            for i in range(0, len(texts), BATCH_SIZE):
                batch = texts[i : i + BATCH_SIZE]
                batch_vectors = list(model.embed(batch))
                for v in batch_vectors:
                    # Ensure float list
                    norm = math.sqrt(sum(float(x) * float(x) for x in v))
                    if norm > 0:
                        results.append([float(x) / norm for x in v])
                    else:
                        results.append([float(x) for x in v])
            return results
        except Exception as exc:
            logger.warning("FastEmbed batch failed (%s); falling back: %s", type(exc).__name__, exc)

    return [_fallback_embedding(t, EMBEDDING_DIMENSIONS) for t in texts]