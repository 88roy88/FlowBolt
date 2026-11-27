"""Enforces the disable_workspaces kill switch and its disable_workspaces_exempt whitelist."""

import time

from fastapi import HTTPException

from flow44.feature_flags import FeatureFlag, is_feature_enabled

# The preview proxy checks this once per asset, so the answer is cached to spare an overloaded backend.
_TTL_SECONDS = 5.0
_cache: dict[str, tuple[float, bool]] = {}

_DISABLED_DETAIL = {"code": "workspaces_disabled", "message": "Workspaces are temporarily unavailable"}


async def are_workspaces_disabled(user_id: str) -> bool:
    now = time.monotonic()
    cached = _cache.get(user_id)
    if cached is not None and cached[0] > now:
        return cached[1]
    # The whitelist is only looked up once the switch applies, so it costs nothing the rest of the time.
    disabled = await is_feature_enabled(user_id, FeatureFlag.disable_workspaces) and not await is_feature_enabled(
        user_id, FeatureFlag.disable_workspaces_exempt
    )
    _cache[user_id] = (now + _TTL_SECONDS, disabled)
    return disabled


async def require_workspaces_enabled(user_id: str) -> None:
    if await are_workspaces_disabled(user_id):
        raise HTTPException(status_code=503, detail=_DISABLED_DETAIL)


def clear_workspace_gate_cache() -> None:
    """Apply a flag change on this pod right away; other pods catch up within the TTL."""
    _cache.clear()
