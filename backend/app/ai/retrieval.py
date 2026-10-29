import uuid
from typing import List, Dict, Any, Optional
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.db.models import DocumentChunk
from app.ingestion.embed import embed_query

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

async def retrieve_document_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    top_k: int = 6
) -> List[DocumentChunk]:
    """
    Document-scoped hybrid retrieval:
    1. Embeds query with RETRIEVAL_QUERY.
    2. Retrieves candidate chunks for document (per-user authorized).
    3. Computes hybrid score: 0.7 * cosine_sim + 0.3 * keyword_score.
    4. Keeps top 6, and pulls in neighbors (chunk_index +- 1) of top 2 for continuity.
    """
    query_emb = await embed_query(query)

    stmt = select(DocumentChunk).where(
        DocumentChunk.document_id == document_id,
        DocumentChunk.user_id == user_id
    ).order_by(DocumentChunk.chunk_index.asc())
    
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    if not chunks:
        return []

    # Score chunks
    scored_chunks = []
    q_words = set(query.lower().split())

    for c in chunks:
        # Cosine similarity
        c_emb = c.embedding
        if isinstance(c_emb, list):
            cos_sim = cosine_similarity(query_emb, c_emb)
        else:
            cos_sim = 0.5  # fallback if vector was stored as text/empty

        # Keyword overlap proxy for ts_rank_cd
        c_words = set(c.content.lower().split())
        overlap = len(q_words.intersection(c_words)) / max(1, len(q_words))
        
        hybrid_score = 0.7 * cos_sim + 0.3 * overlap
        scored_chunks.append((c, hybrid_score))

    # Sort descending
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    top_candidates = [c for c, score in scored_chunks[:top_k]]

    # Continuity: pull in neighbors (chunk_index +- 1) of top 2
    if len(top_candidates) >= 1:
        top_indices = {top_candidates[0].chunk_index}
        if len(top_candidates) >= 2:
            top_indices.add(top_candidates[1].chunk_index)

        neighbor_indices = set()
        for idx in top_indices:
            neighbor_indices.add(idx - 1)
            neighbor_indices.add(idx + 1)

        # Find any neighbor chunks not yet included
        candidate_ids = {c.id for c in top_candidates}
        for c in chunks:
            if c.chunk_index in neighbor_indices and c.id not in candidate_ids:
                top_candidates.append(c)

    return top_candidates

async def retrieve_chapter_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
    heading_prefix: Optional[str] = None
) -> List[DocumentChunk]:
    """
    Chapter-wide generation does not use similarity at all.
    Selects chunks in chunk_index order so nothing is omitted.
    """
    stmt = select(DocumentChunk).where(
        DocumentChunk.document_id == document_id,
        DocumentChunk.user_id == user_id
    ).order_by(DocumentChunk.chunk_index.asc())

    result = await db.execute(stmt)
    chunks = result.scalars().all()

    if heading_prefix:
        filtered = [
            c for c in chunks
            if any(heading_prefix.lower() in h.lower() for h in (c.heading_path or []))
        ]
        return filtered if filtered else chunks

    return chunks
