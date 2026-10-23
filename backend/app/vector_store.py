"""
Vector Store — Lumio Backend
==============================

Persistent, hybrid retrieval engine combining local ONNX dense embeddings
(BAAI/bge-small-en-v1.5) with BM25 keyword matching fused via Reciprocal
Rank Fusion (RRF), backed by disk-persisted SQLite storage.

Capabilities:
1. **Disk Persistence**: Stores all chunks, metadata, and normalized float vectors
   in SQLite (``lumio_index.db``). Server restarts retain documents and indices.
2. **Hybrid Search (Dense + BM25 + RRF)**:
   - Dense vector cosine similarity handles conceptual and semantic questions.
   - BM25Okapi handles exact academic terms, formulas, names, and equations.
   - Reciprocal Rank Fusion (RRF) combines both rankings with calibrated weights.
3. **Calibrated Similarity Thresholding**:
   - Queries with insufficient relevance score are safely rejected, enabling
     Ask Lumio to report "Not found in this textbook" rather than fabricating facts.
4. **Visual & Structural Relevance**:
   - Questions inquiring about diagrams, figures, or tables receive targeted bonuses.
5. **Session Isolation**:
   - Every store, query, and delete operation is strictly scoped to ``(session_id, document_id)``.
"""

import logging
import math
import re
import sqlite3
import struct
import threading
from pathlib import Path
from typing import Any

from app.config import TEMP_DIR
from app.embedding_generator import EMBEDDING_DIMENSIONS
from rank_bm25 import BM25Okapi

logger = logging.getLogger("lumio.vector_store")

DB_PATH = Path(TEMP_DIR) / "lumio_index.db"
_lock = threading.Lock()

# In-memory fast cache: (session_id, document_id) -> dict with 'records', 'bm25', 'tokens'
_hybrid_cache: dict[tuple[str, str], dict[str, Any]] = {}
_db_initialized = False


# ---------------------------------------------------------------------------
# Database Management
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite vector database."""
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """Create the SQLite chunks table if it does not exist."""
    global _db_initialized
    if _db_initialized:
        return

    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                section TEXT NOT NULL,
                chapter TEXT NOT NULL,
                path TEXT NOT NULL,
                source_pages TEXT NOT NULL,
                printed_pages TEXT NOT NULL,
                has_diagram INTEGER NOT NULL,
                has_table INTEGER NOT NULL,
                embedding BLOB NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_doc ON chunks(session_id, document_id);")
        conn.commit()
    _db_initialized = True


def _pack_vector(vec: list[float]) -> bytes:
    """Pack a list of floats into binary float32 buffer."""
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_vector(blob: bytes) -> list[float]:
    """Unpack binary float32 buffer into list of floats."""
    count = len(blob) // 4
    return list(struct.unpack(f"{count}f", blob))


def _tokenize_for_bm25(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric and symbolic academic terms."""
    return [t.lower() for t in re.findall(r"[\w\u0370-\u03ff\u2070-\u209f]+", text) if len(t) > 1]


def _build_bm25_index(records: list[dict[str, Any]]) -> BM25Okapi | None:
    """Construct a BM25 index from document chunk records."""
    if not records:
        return None
    tokenized = [_tokenize_for_bm25(r["document"]) for r in records]
    # Ensure no empty token list crashes BM25
    clean_tokens = [t if t else ["empty"] for t in tokenized]
    return BM25Okapi(clean_tokens)


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
    Store text chunks and embeddings in persistent SQLite and memory hybrid cache.
    """
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document ID is required")

    if len(chunks) != len(embeddings):
        raise ValueError("The number of chunks must match the number of embeddings")

    if not chunks:
        return 0

    _init_db()
    records = []
    db_rows = []

    for index, chunk in enumerate(chunks):
        text = chunk.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Chunk {index} has missing or empty text")

        embedding = embeddings[index]
        if not embedding:
            raise ValueError(f"Chunk {index} has an empty embedding")

        chunk_id = f"{document_id}_chunk_{index}"
        source_pages = chunk.get("source_pages", [])
        printed_pages = chunk.get("printed_pages", [str(p) for p in source_pages])
        section = chunk.get("section", "Unknown section")
        chapter = chunk.get("chapter", "Document Overview")
        path_str = chunk.get("path") or f"{chapter} > {section}"
        has_diagram = 1 if chunk.get("has_diagram") else 0
        has_table = 1 if chunk.get("has_table") else 0

        source_pages_str = ",".join(str(p) for p in source_pages)
        printed_pages_str = ",".join(str(p) for p in printed_pages)
        blob = _pack_vector(embedding)

        db_rows.append((
            chunk_id, session_id, document_id, index, text, section,
            chapter, path_str, source_pages_str, printed_pages_str,
            has_diagram, has_table, blob
        ))

        records.append({
            "id": chunk_id,
            "embedding": embedding,
            "document": text,
            "metadata": {
                "document_id": document_id,
                "session_id": session_id,
                "section": str(section),
                "chapter": str(chapter),
                "path": str(path_str),
                "source_pages": source_pages_str,
                "printed_pages": printed_pages_str,
                "has_diagram": "true" if has_diagram else "false",
                "has_table": "true" if has_table else "false",
            },
        })

    with _lock:
        with _get_connection() as conn:
            conn.execute("DELETE FROM chunks WHERE session_id = ? AND document_id = ?;", (session_id, document_id))
            conn.executemany("""
                INSERT OR REPLACE INTO chunks (
                    id, session_id, document_id, chunk_index, text, section,
                    chapter, path, source_pages, printed_pages, has_diagram,
                    has_table, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, db_rows)
            conn.commit()

        # Update hybrid in-memory cache
        cache_key = (session_id, document_id)
        _hybrid_cache[cache_key] = {
            "records": records,
            "bm25": _build_bm25_index(records),
        }

    return len(records)


# ---------------------------------------------------------------------------
# Retrieval with Dense + BM25 + Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def _load_records_for_doc(session_id: str, document_id: str) -> list[dict[str, Any]]:
    """Retrieve chunks for a document from in-memory cache or SQLite."""
    cache_key = (session_id, document_id)
    cached = _hybrid_cache.get(cache_key)
    if cached and "records" in cached:
        return cached["records"]

    _init_db()
    records = []
    with _get_connection() as conn:
        cursor = conn.execute("""
            SELECT id, text, section, chapter, path, source_pages,
                   printed_pages, has_diagram, has_table, embedding
            FROM chunks
            WHERE session_id = ? AND document_id = ?
            ORDER BY chunk_index ASC;
        """, (session_id, document_id))
        for row in cursor.fetchall():
            records.append({
                "id": row["id"],
                "embedding": _unpack_vector(row["embedding"]),
                "document": row["text"],
                "metadata": {
                    "document_id": document_id,
                    "session_id": session_id,
                    "section": row["section"],
                    "chapter": row["chapter"],
                    "path": row["path"],
                    "source_pages": row["source_pages"],
                    "printed_pages": row["printed_pages"],
                    "has_diagram": "true" if row["has_diagram"] else "false",
                    "has_table": "true" if row["has_table"] else "false",
                },
            })

    if records:
        _hybrid_cache[cache_key] = {
            "records": records,
            "bm25": _build_bm25_index(records),
        }
    return records


def query_chunks(
    session_id: str,
    document_id: str,
    embedding: list[float],
    limit: int = 6,
    query_text: str = "",
) -> list[dict]:
    """
    Retrieve nearest chunks using Dense Vector similarity + BM25 keyword matching
    fused with Reciprocal Rank Fusion (RRF).
    """
    with _lock:
        records = _load_records_for_doc(session_id, document_id)
        cache_key = (session_id, document_id)
        cached_info = _hybrid_cache.get(cache_key)
        bm25 = cached_info.get("bm25") if cached_info else None

    if not records:
        return []

    n_chunks = len(records)

    # 1. Dense Cosine Similarities
    q_norm = math.sqrt(sum(x * x for x in embedding))
    if q_norm == 0:
        q_norm = 1.0
    normalized_q = [x / q_norm for x in embedding]

    dense_similarities = []
    for i, r in enumerate(records):
        doc_emb = r["embedding"]
        # If lengths match, compute dot product
        if len(doc_emb) == len(normalized_q):
            dot = sum(a * b for a, b in zip(normalized_q, doc_emb))
            dense_similarities.append((dot, i))
        else:
            dense_similarities.append((0.0, i))

    dense_similarities.sort(key=lambda x: -x[0])
    dense_rank_map = {idx: rank + 1 for rank, (_, idx) in enumerate(dense_similarities)}

    # 2. BM25 Keyword Scoring
    query_tokens = _tokenize_for_bm25(query_text) if query_text else []
    bm25_rank_map = {}
    max_bm25 = 0.0

    if bm25 and query_tokens:
        bm25_scores = bm25.get_scores(query_tokens)
        max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 else 0.0
        sorted_bm25 = sorted(enumerate(bm25_scores), key=lambda x: -x[1])
        bm25_rank_map = {idx: rank + 1 for rank, (idx, score) in enumerate(sorted_bm25)}
    else:
        bm25_rank_map = {i: i + 1 for i in range(n_chunks)}

    # 3. Reciprocal Rank Fusion (RRF)
    # k = 60 is standard RRF constant
    k = 60.0
    scored = []
    q_lower = query_text.lower() if query_text else ""
    is_diagram_q = any(w in q_lower for w in ["diagram", "figure", "fig", "draw", "plot", "image"])
    is_table_q = any(w in q_lower for w in ["table", "column", "row", "geometry", "angle"])

    for i, r in enumerate(records):
        r_dense = dense_rank_map[i]
        r_bm25 = bm25_rank_map.get(i, n_chunks)

        dense_score = 1.0 / (k + r_dense)
        bm25_score = 1.0 / (k + r_bm25) if query_tokens else 0.0

        rrf_score = dense_score + (1.2 * bm25_score)

        # Visual bonuses
        meta = r["metadata"]
        if is_diagram_q and (meta.get("has_diagram") == "true" or "[figure" in r["document"].lower()):
            rrf_score += 0.012
        if is_table_q and (meta.get("has_table") == "true" or "| --- |" in r["document"]):
            rrf_score += 0.012

        # Convert RRF score to normalized effective distance (lower is closer)
        # Max theoretical score is ~ 1/61 + 1.2/61 + 0.024 ~= 0.06
        effective_dist = max(0.0, 1.0 - (rrf_score / 0.045))

        scored.append({
            "text": r["document"],
            "metadata": meta,
            "distance": round(effective_dist, 5),
            "rrf_score": rrf_score,
        })

    # Calibrated relevance cutoff:
    # If best dense similarity < 0.20 and BM25 score is 0, query is completely irrelevant
    best_dense_sim = dense_similarities[0][0] if dense_similarities else 0.0
    if query_text and best_dense_sim < 0.20 and max_bm25 == 0.0:
        return []

    scored.sort(key=lambda x: -x["rrf_score"])
    return scored[:limit]


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------

def delete_document(document_id: str, session_id: str) -> None:
    """Delete all stored chunks belonging to one document within a session."""
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document ID is required")

    _init_db()
    with _lock:
        with _get_connection() as conn:
            conn.execute("DELETE FROM chunks WHERE session_id = ? AND document_id = ?;", (session_id, document_id))
            conn.commit()
        cache_key = (session_id, document_id)
        _hybrid_cache.pop(cache_key, None)


def clear_all_chunks() -> None:
    """Purge every chunk in both SQLite database and in-memory cache."""
    _init_db()
    with _lock:
        with _get_connection() as conn:
            conn.execute("DELETE FROM chunks;")
            conn.commit()
        _hybrid_cache.clear()