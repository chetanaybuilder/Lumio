import json
from functools import lru_cache
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import GEMINI_API_KEY, GEMINI_MODEL


T = TypeVar("T", bound=BaseModel)
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768


@lru_cache(maxsize=1)
def get_client():
    if not GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured. Set GEMINI_API_KEY and restart the API.")
    return genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 30000})


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    if not texts:
        return []
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


def generate_structured(prompt: str, output_type: type[T]) -> T:
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


# Keep Gemini configuration and failure handling centralized.