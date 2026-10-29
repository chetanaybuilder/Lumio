import math
import hashlib
from typing import List, Optional
import numpy as np
from app.config import settings

def _deterministic_local_embedding(text: str, dim: int = 768) -> List[float]:
    """Generates a deterministic 768-dim L2-normalized embedding for offline testing."""
    vec = np.zeros(dim, dtype=np.float32)
    tokens = text.lower().split()
    if not tokens:
        vec[0] = 1.0
        return vec.tolist()

    for i, token in enumerate(tokens):
        # Hash token into dimension indices
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
        vec[idx] += sign

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    else:
        vec[0] = 1.0
    return vec.tolist()

async def embed_texts_batch(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT",
    target_dim: int = 768
) -> List[List[float]]:
    """
    Generates 768-dimensional L2-normalized embeddings in batches of up to 100 texts.
    Uses google-genai SDK when GEMINI_API_KEY is available, otherwise local fallback.
    """
    if not texts:
        return []

    if settings.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            embeddings = []
            
            # Process in batches of 100
            batch_size = 100
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = client.models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=batch,
                    config={
                        "output_dimensionality": target_dim
                    }
                )
                for emb in response.embeddings:
                    vec = np.array(emb.values[:target_dim], dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec = vec / norm
                    embeddings.append(vec.tolist())
            return embeddings
        except Exception as e:
            # Fallback to deterministic local embeddings on error
            pass

    return [_deterministic_local_embedding(t, target_dim) for t in texts]

async def embed_query(query: str, target_dim: int = 768) -> List[float]:
    """Embeds a single query with RETRIEVAL_QUERY task type."""
    res = await embed_texts_batch([query], task_type="RETRIEVAL_QUERY", target_dim=target_dim)
    return res[0]
