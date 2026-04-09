"""REST endpoints for available AI models."""

from __future__ import annotations

import logging
import time
from typing import Any, cast

import httpx
from fastapi import APIRouter

from flow44.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_cache: dict[str, Any] = {"models": [], "ts": 0.0}
_CACHE_TTL = 60  # seconds


def _cache_valid() -> bool:
    return bool((time.monotonic() - _cache["ts"]) < _CACHE_TTL)


# ---------------------------------------------------------------------------
# Bedrock discovery
# ---------------------------------------------------------------------------

# Map of known Anthropic model-id fragments to friendly display names.
# Falls back to the raw modelId if no match is found.
# Ordered most-specific first so longer fragments match before shorter ones.
_BEDROCK_FRIENDLY_NAMES: list[tuple[str, str]] = [
    ("claude-opus-4-6", "Claude Opus 4.6"),
    ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
    ("claude-haiku-4-5", "Claude Haiku 4.5"),
    ("claude-opus-4-0", "Claude Opus 4.0"),
    ("claude-sonnet-4-0", "Claude Sonnet 4.0"),
    ("claude-opus-4", "Claude Opus 4"),
    ("claude-sonnet-4", "Claude Sonnet 4"),
    ("claude-haiku-4", "Claude Haiku 4"),
    ("claude-3-7-sonnet", "Claude 3.7 Sonnet"),
    ("claude-3-5-sonnet", "Claude 3.5 Sonnet"),
    ("claude-3-5-haiku", "Claude 3.5 Haiku"),
    ("claude-3-opus", "Claude 3 Opus"),
    ("claude-3-sonnet", "Claude 3 Sonnet"),
    ("claude-3-haiku", "Claude 3 Haiku"),
    ("claude-v2", "Claude 2"),
    ("claude-v1", "Claude 1"),
    ("claude-instant", "Claude Instant"),
]


def _friendly_name(model_id: str) -> str:
    """Derive a human-friendly name from a Bedrock model ID."""
    for fragment, name in _BEDROCK_FRIENDLY_NAMES:
        if fragment in model_id:
            return name
    # Fallback: strip provider prefix, replace dots/dashes
    return model_id.replace("anthropic.", "").rsplit("-", 1)[0].replace("-", " ").title()


def _fetch_bedrock_models() -> list[dict[str, str]]:
    """Query AWS Bedrock for available Anthropic cross-region inference profiles."""
    try:
        import boto3  # noqa: F811, PLC0415
    except ImportError:
        logger.warning("boto3 is not installed; skipping Bedrock model discovery")
        return []

    try:
        client = boto3.client("bedrock")
        response = client.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
        models: list[dict[str, str]] = []
        for profile in response.get("inferenceProfileSummaries", []):
            profile_id: str = profile.get("inferenceProfileId", "")
            # Only show US cross-region Anthropic profiles
            if not profile_id.startswith("us.anthropic."):
                continue
            models.append(
                {
                    "id": f"bedrock/{profile_id}",
                    "name": f"{_friendly_name(profile_id)} ({profile_id})",
                    "provider": "bedrock",
                }
            )
        return models
    except Exception:
        logger.warning("Failed to list Bedrock models (AWS credentials missing or invalid?)", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Ollama discovery
# ---------------------------------------------------------------------------


def _fetch_models_from_base_url() -> list[dict[str, str]]:
    """Query AI_BASE_URL/models endpoint for available models (OpenAI-compatible)."""
    if not settings.AI_BASE_URL or not settings.AI_API_KEY:
        return []

    # Construct the /models endpoint URL
    base_url = settings.AI_BASE_URL.rstrip("/")
    models_url = f"{base_url}/models"

    # Extract provider name from hostname (e.g., "openrouter.ai" -> "openrouter")
    try:
        from urllib.parse import urlparse  # noqa: PLC0415

        parsed = urlparse(base_url)
        hostname = parsed.hostname or "custom"
        provider_name = hostname.split(".")[0] if "." in hostname else hostname
    except Exception:
        provider_name = "custom"

    try:
        headers = {"Authorization": settings.AI_API_KEY}
        resp = httpx.get(models_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        models: list[dict[str, str]] = []
        for entry in data.get("data", []):
            model_id: str = entry.get("id", "")
            if not model_id:
                continue

            # Extract friendly name if available, otherwise use ID
            name = entry.get("name", model_id)

            # Prepend openai/ for OpenAI-compatible models (testing if this works with api_base)
            full_model_id = f"openai/{model_id}"

            models.append(
                {
                    "id": full_model_id,
                    "name": name,
                    "provider": provider_name,
                }
            )

        logger.info("Fetched %d models from %s", len(models), models_url)
        return models
    except Exception:
        logger.warning("Failed to list models from %s (check AI_BASE_URL and AI_API_KEY)", models_url, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# OpenRouter static models
# ---------------------------------------------------------------------------


def _get_openrouter_models() -> list[dict[str, str]]:
    """Return a static list of OpenRouter models."""
    return [
        {
            "id": "openrouter/minimax/minimax-m2.5",
            "name": "Minimax M2.5 (OpenRouter)",
            "provider": "openrouter",
        },
        {
            "id": "openrouter/z-ai/glm-4.7",
            "name": "GLM-4.7 (OpenRouter)",
            "provider": "openrouter",
        },
        {
            "id": "openrouter/qwen/qwen3-coder-30b-a3b-instruct",
            "name": "Qwen3 Coder 30B (OpenRouter)",
            "provider": "openrouter",
        },
    ]


# ---------------------------------------------------------------------------
# Aggregation with caching
# ---------------------------------------------------------------------------


def _refresh_models() -> list[dict[str, str]]:
    """Fetch models from all providers and update the cache."""
    all_models: list[dict[str, str]] = []

    # If using Bedrock, fetch Bedrock models; otherwise fetch from AI_BASE_URL
    if settings.AI_MODEL.startswith("bedrock"):
        all_models.extend(_fetch_bedrock_models())
    else:
        all_models.extend(_fetch_models_from_base_url())

    _cache["models"] = all_models
    _cache["ts"] = time.monotonic()
    return all_models


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/models")
async def list_models() -> list[dict[str, str]]:
    """Return the list of available AI models (cached for 60 s)."""
    if _cache_valid():
        return cast(list[dict[str, str]], _cache["models"])
    return _refresh_models()


@router.get("/api/models/default")
async def default_model() -> dict[str, str]:
    """Return the default model from settings."""
    return {"model": settings.AI_MODEL}
