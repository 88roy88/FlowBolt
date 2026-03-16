"""REST endpoints for available AI models."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_cache: dict[str, Any] = {"models": [], "ts": 0.0}
_CACHE_TTL = 60  # seconds


def _cache_valid() -> bool:
    return (time.monotonic() - _cache["ts"]) < _CACHE_TTL


# ---------------------------------------------------------------------------
# Bedrock discovery
# ---------------------------------------------------------------------------

# Map of known Anthropic model-id fragments to friendly display names.
# Falls back to the raw modelId if no match is found.
_BEDROCK_FRIENDLY_NAMES: dict[str, str] = {
    "claude-opus-4": "Claude Opus 4",
    "claude-sonnet-4": "Claude Sonnet 4",
    "claude-haiku-4": "Claude Haiku 4",
    "claude-3-5-sonnet": "Claude 3.5 Sonnet",
    "claude-3-5-haiku": "Claude 3.5 Haiku",
    "claude-3-opus": "Claude 3 Opus",
    "claude-3-sonnet": "Claude 3 Sonnet",
    "claude-3-haiku": "Claude 3 Haiku",
    "claude-v2": "Claude 2",
    "claude-v1": "Claude 1",
    "claude-instant": "Claude Instant",
}


def _friendly_name(model_id: str) -> str:
    """Derive a human-friendly name from a Bedrock model ID."""
    for fragment, name in _BEDROCK_FRIENDLY_NAMES.items():
        if fragment in model_id:
            return name
    # Fallback: strip provider prefix, replace dots/dashes
    return model_id.replace("anthropic.", "").rsplit("-", 1)[0].replace("-", " ").title()


def _fetch_bedrock_models() -> list[dict[str, str]]:
    """Query AWS Bedrock for available Anthropic foundation models."""
    try:
        import boto3  # noqa: F811
    except ImportError:
        logger.warning("boto3 is not installed; skipping Bedrock model discovery")
        return []

    try:
        client = boto3.client("bedrock")
        response = client.list_foundation_models(byProvider="Anthropic")
        models: list[dict[str, str]] = []
        for summary in response.get("modelSummaries", []):
            model_id: str = summary.get("modelId", "")
            if not model_id:
                continue
            models.append(
                {
                    "id": f"bedrock/{model_id}",
                    "name": f"{_friendly_name(model_id)} ({model_id})",
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


def _fetch_ollama_models() -> list[dict[str, str]]:
    """Query the local Ollama instance for available models."""
    url = f"{settings.OLLAMA_BASE_URL}/api/tags"
    try:
        resp = httpx.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models: list[dict[str, str]] = []
        for entry in data.get("models", []):
            name: str = entry.get("name", "")
            if not name:
                continue
            models.append(
                {
                    "id": f"ollama/{name}",
                    "name": f"ollama/{name}",
                    "provider": "ollama",
                }
            )
        return models
    except Exception:
        logger.warning("Failed to list Ollama models (is Ollama running at %s?)", settings.OLLAMA_BASE_URL, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Aggregation with caching
# ---------------------------------------------------------------------------


def _refresh_models() -> list[dict[str, str]]:
    """Fetch models from all providers and update the cache."""
    all_models: list[dict[str, str]] = []
    all_models.extend(_fetch_bedrock_models())
    all_models.extend(_fetch_ollama_models())
    _cache["models"] = all_models
    _cache["ts"] = time.monotonic()
    return all_models


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/models")
async def list_models() -> list[dict]:
    """Return the list of available AI models (cached for 60 s)."""
    if _cache_valid():
        return _cache["models"]
    return _refresh_models()


@router.get("/api/models/default")
async def default_model() -> dict:
    """Return the default model from settings."""
    return {"model": settings.AI_MODEL}
