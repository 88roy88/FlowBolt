"""The current user's identity and access flags."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from flow44.api.deps import UserDep, can_use_terminal, has_platform_access, is_admin, terminal_admin_only

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me")
async def get_current_user(user_id: UserDep) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "is_admin": is_admin(user_id),
        "is_platform_user": await has_platform_access(user_id),
        "can_use_terminal": can_use_terminal(user_id),
        "terminal_admin_only": terminal_admin_only(),
    }
