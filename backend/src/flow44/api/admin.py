from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.api.deps import UserDep
from flow44.config import settings
from flow44.db.platform_user import (
    add_platform_user,
    list_platform_users,
    remove_platform_user,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user_id: str) -> None:
    if user_id not in settings.SYSTEM_ADMIN_IDS:
        raise HTTPException(status_code=403, detail="Admin access required")


class InviteUserRequest(BaseModel):
    user_id: str


class PlatformUserResponse(BaseModel):
    user_id: str
    invited_by: str
    created_at: str


@router.get("/users")
async def list_users(user_id: UserDep) -> list[PlatformUserResponse]:
    _require_admin(user_id)
    users = await list_platform_users()
    return [PlatformUserResponse(user_id=u.user_id, invited_by=u.invited_by, created_at=u.created_at) for u in users]


@router.post("/users", status_code=201)
async def invite_user(user_id: UserDep, body: InviteUserRequest) -> PlatformUserResponse:
    _require_admin(user_id)
    user = await add_platform_user(user_id=body.user_id, invited_by=user_id)
    return PlatformUserResponse(user_id=user.user_id, invited_by=user.invited_by, created_at=user.created_at)


@router.delete("/users/{target_user_id}", status_code=204)
async def revoke_user(user_id: UserDep, target_user_id: str) -> None:
    _require_admin(user_id)
    removed = await remove_platform_user(target_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="User not found")
