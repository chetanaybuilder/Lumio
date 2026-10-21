"""
Vector Store — Lumio Backend
==============================

In-memory vector store that stores document chunk embeddings and performs
nearest-neighbor retrieval using cosine similarity.  All operations are
scoped to a ``(session_id, document_id)`` pair so that:

- Different sessions cannot access each other's documents.
- A single session can store and query multiple documents independently.
- Cleanup (deletion, expiry) can target a specific document or an entire
  session's data without affecting other users.

This implementation uses pure Python with no native dependencies, making
it compatible with Cloudflare Workers (Pyodide / WebAssembly) and any
standard Python environment.

Functions
---------
store_chunks    : Insert chunk embeddings with metadata.
query_chunks    : Retrieve nearest-neighbor chunks for a query embedding.
delete_document : Remove all chunks belonging to one document + session.
clear_all_chunks: Purge the entire store (used at backend startup).
"""

import math
import threading

from app.gemini_client import EMBEDDING_DIMENSIONS


# ---------------------------------------------------------------------------
# Thread-safe in-memory store
# ---------------------------------------------------------------------------

# Global store: list of chunk records.
# Each record: {"id": str, "embedding": list[float], "document": str,
#               "metadata": dict}
_store: list[dict] = []
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Cosine similarity helper
# ---------------------------------------------------------------------------

def _cosine_distance(a: list[float], b: list[float]) -> float:
    """
    Compute cosine distance between two vectors.

    Returns a value between 0.0 (identical) and 2.0 (opposite).
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    similarity = dot / (norm_a * norm_b)
    # Clamp to avoid floating-point issues.
    return 1.0 - max(-1.0, min(1.0, similarity))


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_chunks(
    document_id: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    session_id: str,
) -> int:
    """
    Store text chunks and their embeddings in the in-memory vector store.

    Each chunk is stored with metadata including ``document_id``,
    ``session_id``, ``section`` heading, and comma-separated
    ``source_pages``.  The chunk ID is deterministic:
    ``{document_id}_chunk_{index}``.

    Parameters
    ----------
    document_id : str
        Unique identifier for the uploaded document.
    chunks : list[dict]
        Chunk dictionaries with ``"text"``, ``"section"``, and
        ``"source_pages"`` keys.
    embeddings : list[list[float]]
        Embedding vectors — must be the same length as *chunks*.
    session_id : str
        The owning session's token for access-control filtering.

    Returns
    -------
    int
        The number of chunks successfully stored.

    Raises
    ------
    ValueError
        If inputs are invalid (empty ID, mismatched lengths, bad vectors).
    """
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document ID is required")

    if len(chunks) != len(embeddings):
        raise ValueError("The number of chunks must match the number of embeddings")

    if not chunks:
        return 0

    records = []

    for index, chunk in enumerate(chunks):
        text = chunk.get("text")

        # Reject chunks with missing or empty text.
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Chunk {index} has missing or empty text")

        embedding = embeddings[index]

        # Validate embedding presence and dimensionality.
        if not embedding:
            raise ValueError(f"Chunk {index} has an empty embedding")

        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"Chunk {index} must have a {EMBEDDING_DIMENSIONS}-dimensional embedding")

        # Build deterministic chunk ID for idempotent upserts.
        chunk_id = f"{document_id}_chunk_{index}"

        source_pages = chunk.get("source_pages", [])
        section = chunk.get("section", "Unknown section")

        records.append({
            "id": chunk_id,
            "embedding": embedding,
            "document": text,
            "metadata": {
                "document_id": document_id,
                "session_id": session_id,
                "section": str(section),
                "source_pages": ",".join(str(page) for page in source_pages),
            },
        })

    with _lock:
        # Remove any existing records with the same IDs (upsert behavior).
        existing_ids = {record["id"] for record in records}
        _store[:] = [r for r in _store if r["id"] not in existing_ids]
        _store.extend(records)

    return len(records)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def query_chunks(session_id: str, document_id: str, embedding: list[float], limit: int = 6) -> list[dict]:
    """
    Retrieve the nearest chunks to a query embedding.

    Results are filtered to the specified session and document so that
    cross-session access is impossible at the vector-store level.

    Parameters
    ----------
    session_id : str
        The requesting session's token.
    document_id : str
        The target document's ID.
    embedding : list[float]
        The 768-dimensional query embedding.
    limit : int, optional
        Maximum number of results to return (default 6).

    Returns
    -------
    list[dict]
        Matches with ``"text"``, ``"metadata"``, and ``"distance"`` keys,
        ordered by ascending distance (closest first).
    """
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError("Query embedding has an invalid dimension")

    with _lock:
        candidates = [
            r for r in _store
            if r["metadata"]["session_id"] == session_id
            and r["metadata"]["document_id"] == document_id
        ]

    # Compute cosine distance for each candidate.
    scored = [
        {
            "text": record["document"],
            "metadata": record["metadata"],
            "distance": _cosine_distance(embedding, record["embedding"]),
        }
        for record in candidates
    ]

    # Sort by distance (closest first) and return top results.
    scored.sort(key=lambda x: x["distance"])
    return scored[:limit]


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def delete_document(document_id: str, session_id: str) -> None:
    """
    Delete all stored chunks belonging to one document within a session.

    Uses both document_id and session_id filters so that a document ID
    from another session cannot be accidentally (or maliciously) deleted.
    """
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document ID is required")

    with _lock:
        _store[:] = [
            r for r in _store
            if not (
                r["metadata"]["document_id"] == document_id
                and r["metadata"]["session_id"] == session_id
            )
        ]


def clear_all_chunks() -> None:
    """
    Purge every chunk in the store.

    Called at backend startup because in-memory session records do not
    survive restarts, making orphaned vectors unreachable.
    """
    with _lock:
        _store.clear()


# Every retrieval and cleanup operation is scoped to a session and document.