import time

from fastapi import HTTPException

from flow44.feature_flags import FeatureFlag, is_feature_enabled

_TTL_SECONDS = 5.0
_cache: dict[str, tuple[float, bool]] = {}

_DISABLED_DETAIL = {"code": "workspaces_disabled", "message": "Workspaces are temporarily unavailable"}


async def are_workspaces_disabled(user_id: str) -> bool:
    now = time.monotonic()
    cached = _cache.get(user_id)
    if cached is not None and cached[0] > now:
        return cached[1]
    disabled = await is_feature_enabled(user_id, FeatureFlag.workspace_blacklist) and not await is_feature_enabled(
        user_id, FeatureFlag.workspace_whitelist
    )
    _cache[user_id] = (now + _TTL_SECONDS, disabled)
    return disabled


async def require_workspaces_enabled(user_id: str) -> None:
    if await are_workspaces_disabled(user_id):
        raise HTTPException(status_code=503, detail=_DISABLED_DETAIL)
