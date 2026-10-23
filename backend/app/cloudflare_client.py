"""
Cloudflare Workers AI Client — Lumio Backend
============================================

Provides serverless LLM inference powered by Cloudflare Workers AI with:
1. Structured JSON output generation validated against Pydantic models.
2. Primary inference via @cf/meta/llama-3.3-70b-instruct-fp8-fast.
3. Automatic fallback to @cf/meta/llama-3.1-8b-instruct-fp8 if primary model hits rate limits.
4. Exponential backoff and jitter on 429/5xx.
5. Robust JSON sanitization and repair for clean Pydantic validation.
"""

import json
import logging
import os
import random
import re
import time
from pathlib import Path
from typing import TypeVar

import httpx
from app.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_FALLBACK_MODEL,
    CLOUDFLARE_MODEL,
)
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("lumio.cloudflare_ai")

T = TypeVar("T", bound=BaseModel)

EMBEDDING_DIMENSIONS = 384


def _resolve_api_token() -> str:
    """Resolve Cloudflare API token from environment or local wrangler credentials."""
    if CLOUDFLARE_API_TOKEN:
        return CLOUDFLARE_API_TOKEN

    token_from_env = os.getenv("CLOUDFLARE_API_TOKEN") or os.getenv("CF_API_TOKEN")
    if token_from_env:
        return token_from_env

    # Check for local wrangler oauth token in user profile
    wrangler_cfg = Path.home() / "AppData" / "Roaming" / "xdg.config" / ".wrangler" / "config" / "default.toml"
    if not wrangler_cfg.exists():
        wrangler_cfg = Path.home() / ".config" / ".wrangler" / "config" / "default.toml"

    if wrangler_cfg.exists():
        try:
            content = wrangler_cfg.read_text(encoding="utf-8")
            match = re.search(r'oauth_token\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
        except Exception as exc:
            logger.debug("Could not read wrangler default.toml: %s", exc)

    return ""


def _resolve_account_id() -> str:
    """Resolve Cloudflare Account ID from config or environment."""
    if CLOUDFLARE_ACCOUNT_ID:
        return CLOUDFLARE_ACCOUNT_ID
    return os.getenv("CLOUDFLARE_ACCOUNT_ID") or os.getenv("CF_ACCOUNT_ID") or ""


def _sanitize_json(raw: str) -> str:
    """Strip markdown code fences, think tags, and clean trailing whitespace."""
    text = raw.strip()
    # Strip DeepSeek or Qwen reasoning/thinking tags if present
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
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
    Prompt Cloudflare Workers AI for a structured JSON response and validate it against *output_type*.
    Handles rate-limiting with exponential backoff and falls back to a fast model if needed.
    """
    token = _resolve_api_token()
    account_id = _resolve_account_id()

    if not token or not account_id:
        raise RuntimeError(
            "Cloudflare Workers AI is not fully configured. "
            "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in backend/.env."
        )

    endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Lumio-Study-AI/1.0",
    }

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

    models_to_try = [CLOUDFLARE_MODEL]
    if CLOUDFLARE_FALLBACK_MODEL and CLOUDFLARE_FALLBACK_MODEL != CLOUDFLARE_MODEL:
        models_to_try.append(CLOUDFLARE_FALLBACK_MODEL)

    last_error = None
    max_attempts = 4

    # Cap prompt content to fit comfortably within model context windows
    if len(prompt) > 9000:
        prompt_content = prompt[:9000] + "\n...[Context trimmed to fit token limit]..."
    else:
        prompt_content = prompt

    for attempt in range(max_attempts):
        current_model = models_to_try[0] if attempt < 2 else models_to_try[-1]

        payload = {
            "model": current_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt_content},
            ],
            "temperature": 0.15,
            "max_tokens": 2500,
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(endpoint, headers=headers, json=payload)

            if res.status_code == 429 or res.status_code >= 500:
                backoff = (2 ** attempt) * 0.75 + random.uniform(0.1, 0.5)
                logger.warning(
                    "Cloudflare AI HTTP %d on model %s; backing off %.2fs (attempt %d/%d)",
                    res.status_code, current_model, backoff, attempt + 1, max_attempts
                )
                time.sleep(backoff)
                last_error = RuntimeError(f"HTTP {res.status_code}: {res.text[:200]}")
                continue

            if res.status_code != 200:
                err_text = res.text[:300]
                logger.warning("Cloudflare AI error (%d): %s", res.status_code, err_text)
                last_error = RuntimeError(f"Cloudflare AI error {res.status_code}: {err_text}")
                time.sleep(0.5)
                continue

            data = res.json()
            raw_text = ""
            if "choices" in data and len(data["choices"]) > 0:
                raw_text = data["choices"][0].get("message", {}).get("content", "")
            elif "result" in data and isinstance(data["result"], dict):
                raw_text = data["result"].get("response", "")

            cleaned = _sanitize_json(raw_text)

            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as decode_err:
                logger.warning("JSON decode failed on attempt %d: %s", attempt + 1, decode_err)
                last_error = decode_err
                time.sleep(0.5)
                continue

            return output_type.model_validate(parsed)

        except ValidationError as val_err:
            logger.warning("Pydantic validation error on attempt %d: %s", attempt + 1, val_err)
            last_error = val_err
            time.sleep(0.5)
            continue

        except Exception as exc:
            logger.warning("Cloudflare AI call failed on attempt %d: %s", attempt + 1, exc)
            last_error = exc
            time.sleep(0.5)

    raise RuntimeError(f"Structured generation failed after {max_attempts} attempts: {last_error}")
