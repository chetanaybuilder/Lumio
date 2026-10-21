"""
Groq Client — Lumio Backend
===========================

Provides high-speed LLM inference powered by Groq LPUs and deterministic
local feature embeddings:

1. **Local Embeddings** — microsecond deterministic vectorization (256-dim)
   using normalized n-gram feature hashing for in-memory cosine similarity search.
   Zero external network calls, zero latency, zero rate limits.
2. **Structured Generation** — sub-second prompting via Groq's high-speed
   inference engine (default ``openai/gpt-oss-20b`` or ``qwen/qwen3.8-27b``),
   validated against Pydantic models for type-safe notes, quizzes, flashcards,
   and chat answers under 5 seconds.
"""

import hashlib
import json
import logging
import math
import re
from functools import lru_cache
from typing import TypeVar

from groq import Groq
from pydantic import BaseModel, ValidationError

from app.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Vector embedding dimensions
# ---------------------------------------------------------------------------

EMBEDDING_DIMENSIONS = 256


# ---------------------------------------------------------------------------
# Groq client singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_client() -> Groq:
    """Return a cached Groq client instance."""
    if not GROQ_API_KEY:
        raise RuntimeError("Groq is not configured. Set GROQ_API_KEY and restart the API.")
    return Groq(api_key=GROQ_API_KEY, timeout=8.0)


# ---------------------------------------------------------------------------
# Fast local deterministic embedding
# ---------------------------------------------------------------------------

def _vectorize_text(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Compute an L2-normalized n-gram frequency hash embedding."""
    words = re.findall(r"\w+", text.lower())
    if not words:
        return [0.0] * dimensions

    vec = [0.0] * dimensions
    tokens = list(words)
    # Include consecutive bigrams for phrase matching
    for i in range(len(words) - 1):
        tokens.append(f"{words[i]}_{words[i+1]}")

    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dimensions
        vec[h] += 1.0

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [x / norm for x in vec]
    return vec


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Generate normalized embedding vectors for a batch of texts.
    Executes in pure Python with microsecond speed.
    """
    if not texts:
        return []
    return [_vectorize_text(t) for t in texts]


# ---------------------------------------------------------------------------
# High-speed structured generation via Groq
# ---------------------------------------------------------------------------

def generate_structured(prompt: str, output_type: type[T]) -> T:
    """
    Prompt Groq for a structured JSON response and validate it against *output_type*.

    Uses Groq's high-speed inference engine with JSON mode, responding in
    under 5 seconds (typically ~0.8s - 2.5s).
    """
    client = get_client()
    schema_json = json.dumps(output_type.model_json_schema(), indent=2)

    system_instruction = (
        "You are an expert educational AI assistant. "
        "You MUST return ONLY a valid, well-formed JSON object strictly matching this JSON schema:\n"
        f"{schema_json}\n\n"
        "Do NOT include markdown code blocks, fences (no ```json), or any text outside the JSON."
    )

    last_err = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=4096,
            )

            raw_text = response.choices[0].message.content or ""
            # Strip markdown code fences if model accidentally wrapped output
            cleaned_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
            cleaned_text = re.sub(r"\s*```$", "", cleaned_text.strip())

            parsed_data = json.loads(cleaned_text)
            return output_type.model_validate(parsed_data)
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            logger.warning("Groq output schema validation failed (attempt %d): %s", attempt + 1, error)
            last_err = error
            continue
        except Exception as exc:
            logger.warning("Groq API request failed (attempt %d): %s", attempt + 1, exc)
            last_err = exc
            continue

    raise RuntimeError(f"Groq generation failed after retries: {last_err}")
