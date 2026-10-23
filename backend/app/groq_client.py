"""
Groq Client — Lumio Backend
===========================

Provides high-speed LLM inference powered by Groq LPUs with:
1. Structured JSON output generation validated against Pydantic models.
2. Automatic retry with exponential backoff and jitter on 429/5xx.
3. Model fallback to llama-3.1-8b-instant if primary model hits rate limits.
4. Clean JSON sanitization and repair for flawless Pydantic validation.
"""

import json
import logging
import os
import random
import re
import time
from functools import lru_cache
from typing import TypeVar

from app.config import GROQ_API_KEY, GROQ_MODEL
from groq import Groq
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("lumio.groq")

T = TypeVar("T", bound=BaseModel)

EMBEDDING_DIMENSIONS = 384
FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")


@lru_cache(maxsize=1)
def get_client() -> Groq:
    """Return a cached Groq client instance."""
    if not GROQ_API_KEY:
        raise RuntimeError("Groq is not configured. Set GROQ_API_KEY and restart the API.")
    return Groq(api_key=GROQ_API_KEY, timeout=15.0)


def _sanitize_json(raw: str) -> str:
    """Strip markdown code fences and clean trailing whitespace."""
    text = raw.strip()
    # Strip opening fence
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Strip closing fence
    text = re.sub(r"\s*```$", "", text)
    # Find outer bracket/brace if extra commentary was included
    brace_start = text.find("{")
    bracket_start = text.find("[")
    if brace_start != -1 and (bracket_start == -1 or brace_start < bracket_start):
        brace_end = text.rfind("}")
        if brace_end != -1:
            text = text[brace_start : brace_end + 1]
    elif bracket_start != -1:
        bracket_end = text.rfind("]")
        if bracket_end != -1:
            text = text[bracket_start : bracket_end + 1]
    return text.strip()


def generate_structured(prompt: str, output_type: type[T]) -> T:
    """
    Prompt Groq for a structured JSON response and validate it against *output_type*.
    Handles rate-limiting with exponential backoff and falls back to a fast model if needed.
    """
    client = get_client()
    schema_json = json.dumps(output_type.model_json_schema(), indent=2)

    system_instruction = (
        "You are an expert academic professor and elite STEM tutor. "
        "You MUST return ONLY a valid, well-formed JSON object strictly matching this schema:\n"
        f"{schema_json}\n\n"
        "Rules:\n"
        "- Do NOT wrap output in markdown code fences (no ```json).\n"
        "- Do NOT output any text before or after the JSON.\n"
        "- All formulas must be formatted in LaTeX ($...$ or $$...$$).\n"
        "- Output must strictly conform to every schema field."
    )

    models_to_try = [GROQ_MODEL]
    if FALLBACK_MODEL and FALLBACK_MODEL != GROQ_MODEL:
        models_to_try.append(FALLBACK_MODEL)

    last_error = None
    max_attempts = 4

    for attempt in range(max_attempts):
        current_model = models_to_try[0] if attempt < 2 else models_to_try[-1]

        # Context length management: cap prompt to avoid hitting TPM limit
        if len(prompt) > 9000:
            prompt_content = prompt[:9000] + "\n...[Context trimmed to fit token limit]..."
        else:
            prompt_content = prompt

        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt_content},
                ],
                response_format={"type": "json_object"},
                temperature=0.15,
                max_tokens=2200,
            )

            raw_text = response.choices[0].message.content or ""
            cleaned = _sanitize_json(raw_text)

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as decode_err:
                logger.warning("JSON decode failed on attempt %d: %s", attempt + 1, decode_err)
                last_error = decode_err
                continue

            return output_type.model_validate(data)

        except ValidationError as val_err:
            logger.warning("Pydantic validation error on attempt %d: %s", attempt + 1, val_err)
            last_error = val_err
            time.sleep(0.5)
            continue

        except Exception as exc:
            err_msg = str(exc).lower()
            last_error = exc
            is_rate_limit = "429" in err_msg or "rate" in err_msg or "tpm" in err_msg
            is_server_error = "500" in err_msg or "503" in err_msg or "overloaded" in err_msg

            if is_rate_limit or is_server_error:
                backoff = (2 ** attempt) * 0.75 + random.uniform(0.1, 0.5)
                logger.warning(
                    "Groq API error (%s) on model %s; backing off %.2fs (attempt %d/%d)",
                    exc, current_model, backoff, attempt + 1, max_attempts
                )
                time.sleep(backoff)
            else:
                logger.warning("Groq call failed on attempt %d: %s", attempt + 1, exc)
                time.sleep(0.5)

    raise RuntimeError(f"Structured generation failed after {max_attempts} attempts: {last_error}")
