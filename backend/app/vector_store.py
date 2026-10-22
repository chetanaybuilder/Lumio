"""
Vector Store — Lumio Backend
==============================

In-memory vector store that stores document chunk embeddings and performs
hybrid nearest-neighbor retrieval using cosine similarity and technical
keyword / diagram relevance ranking.

All operations are scoped to a ``(session_id, document_id)`` pair so that:
- Different sessions cannot access each other's documents (strict cross-session isolation).
- A single session can store and query multiple documents independently.
- Cleanup (deletion, expiry) targets specific documents or entire sessions cleanly.

Capabilities:
1. **Dense Vector Matching**: Computes cosine distance between query and chunk vectors.
2. **Hybrid Keyword & Diagram Reranking**: If a student's question asks about
   a specific figure, diagram, formula, or table, chunks containing those visual
   elements receive high-relevance boosts.
3. **Thread-Safe & Pure-Python**: Zero native C/C++ dependencies for 100% portability.
"""

import math
import re
import threading

from app.groq_client import EMBEDDING_DIMENSIONS


# ---------------------------------------------------------------------------
# Thread-safe in-memory store
# ---------------------------------------------------------------------------

_store: list[dict] = []
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance between two normalized vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    similarity = dot / (norm_a * norm_b)
    return 1.0 - max(-1.0, min(1.0, similarity))


def _compute_keyword_overlap(query_text: str, document_text: str, metadata: dict) -> float:
    """Compute normalized token overlap between student query and chunk content."""
    if not query_text:
        return 0.0

    query_tokens = set(re.findall(r"\w+", query_text.lower()))
    if not query_tokens:
        return 0.0

    doc_text_lower = document_text.lower()
    doc_tokens = set(re.findall(r"\w+", doc_text_lower))
    section_tokens = set(re.findall(r"\w+", metadata.get("section", "").lower()))

    # Direct token intersection
    matched_doc = query_tokens.intersection(doc_tokens)
    matched_sec = query_tokens.intersection(section_tokens)
    base_overlap = (len(matched_doc) + len(matched_sec) * 1.5) / len(query_tokens)

    # Visual diagram query bonus
    diagram_bonus = 0.0
    is_diagram_query = any(w in query_tokens for w in ["diagram", "figure", "fig", "draw", "graph", "plot", "image", "structure"])
    if is_diagram_query and (metadata.get("has_diagram") == "true" or "[figure" in doc_text_lower):
        diagram_bonus = 0.35

    # Table query bonus
    table_bonus = 0.0
    is_table_query = any(w in query_tokens for w in ["table", "columns", "values", "data", "row"])
    if is_table_query and (metadata.get("has_table") == "true" or "| --- |" in document_text):
        table_bonus = 0.35

    return min(1.0, (base_overlap * 0.7) + diagram_bonus + table_bonus)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_chunks(
    document_id: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    session_id: str,
) -> int:
    """Store text chunks and their embeddings in the in-memory vector store."""
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document ID is required")

    if len(chunks) != len(embeddings):
        raise ValueError("The number of chunks must match the number of embeddings")

    if not chunks:
        return 0

    records = []

    for index, chunk in enumerate(chunks):
        text = chunk.get("text")

        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Chunk {index} has missing or empty text")

        embedding = embeddings[index]

        if not embedding:
            raise ValueError(f"Chunk {index} has an empty embedding")

        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"Chunk {index} must have a {EMBEDDING_DIMENSIONS}-dimensional embedding")

        chunk_id = f"{document_id}_chunk_{index}"
        source_pages = chunk.get("source_pages", [])
        section = chunk.get("section", "Unknown section")
        has_diagram = "true" if chunk.get("has_diagram") else "false"
        has_table = "true" if chunk.get("has_table") else "false"

        records.append({
            "id": chunk_id,
            "embedding": embedding,
            "document": text,
            "metadata": {
                "document_id": document_id,
                "session_id": session_id,
                "section": str(section),
                "source_pages": ",".join(str(page) for page in source_pages),
                "has_diagram": has_diagram,
                "has_table": has_table,
            },
        })

    with _lock:
        existing_ids = {record["id"] for record in records}
        _store[:] = [r for r in _store if r["id"] not in existing_ids]
        _store.extend(records)

    return len(records)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def query_chunks(
    session_id: str,
    document_id: str,
    embedding: list[float],
    limit: int = 6,
    query_text: str = "",
) -> list[dict]:
    """
    Retrieve the nearest chunks to a query embedding with hybrid reranking.

    Parameters
    ----------
    session_id : str
        The requesting session's token.
    document_id : str
        The target document's ID.
    embedding : list[float]
        The query embedding.
    limit : int, optional
        Maximum number of results to return (default 6).
    query_text : str, optional
        The raw user query string for hybrid keyword & diagram bonus scoring.

    Returns
    -------
    list[dict]
        Matches with ``"text"``, ``"metadata"``, and ``"distance"`` keys,
        ordered by ascending distance (most relevant first).
    """
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError("Query embedding has an invalid dimension")

    with _lock:
        candidates = [
            r for r in _store
            if r["metadata"]["session_id"] == session_id
            and r["metadata"]["document_id"] == document_id
        ]

    scored = []
    for record in candidates:
        cos_dist = _cosine_distance(embedding, record["embedding"])
        cos_sim = 1.0 - cos_dist

        if query_text:
            keyword_score = _compute_keyword_overlap(query_text, record["document"], record["metadata"])
            hybrid_score = (0.65 * cos_sim) + (0.35 * keyword_score)
            effective_distance = max(0.0, 1.0 - hybrid_score)
        else:
            effective_distance = cos_dist

        scored.append({
            "text": record["document"],
            "metadata": record["metadata"],
            "distance": effective_distance,
        })

    scored.sort(key=lambda x: x["distance"])
    return scored[:limit]


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def delete_document(document_id: str, session_id: str) -> None:
    """Delete all stored chunks belonging to one document within a session."""
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
    """Purge every chunk in the store."""
    with _lock:
        _store.clear()