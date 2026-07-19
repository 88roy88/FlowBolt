from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from flow44.api.deps import UserDep, is_admin
from flow44.db.platform_user import (
    add_platform_user,
    list_platform_users,
    remove_platform_user,
)
from flow44.db.platform_user_group import (
    add_platform_group,
    list_platform_groups,
    remove_platform_group,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user_id: UserDep) -> str:
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


AdminDep = Annotated[str, Depends(require_admin)]


class InviteUserRequest(BaseModel):
    user_id: str


class PlatformUserResponse(BaseModel):
    user_id: str
    invited_by: str
    created_at: str


class InviteGroupRequest(BaseModel):
    group_id: str  # AD distinguishedName (DN)
    group_name: str = ""


class PlatformGroupResponse(BaseModel):
    group_id: str
    group_name: str
    invited_by: str
    created_at: str


@router.get("/users")
async def list_users(user_id: AdminDep) -> list[PlatformUserResponse]:
    users = await list_platform_users()
    return [PlatformUserResponse(user_id=u.user_id, invited_by=u.invited_by, created_at=u.created_at) for u in users]


@router.post("/users", status_code=201)
async def invite_user(user_id: AdminDep, body: InviteUserRequest) -> PlatformUserResponse:
    try:
        user = await add_platform_user(user_id=body.user_id, invited_by=user_id)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="User already has platform access") from exc
    return PlatformUserResponse(user_id=user.user_id, invited_by=user.invited_by, created_at=user.created_at)


@router.delete("/users/{target_user_id}", status_code=204)
async def revoke_user(user_id: AdminDep, target_user_id: str) -> None:
    removed = await remove_platform_user(target_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="User not found")


# --- Platform group grants (grant platform access to a whole directory group) ---


@router.get("/groups")
async def list_groups(user_id: AdminDep) -> list[PlatformGroupResponse]:
    groups = await list_platform_groups()
    return [
        PlatformGroupResponse(
            group_id=g.group_id, group_name=g.group_name, invited_by=g.invited_by, created_at=g.created_at
        )
        for g in groups
    ]


@router.post("/groups", status_code=201)
async def invite_group(user_id: AdminDep, body: InviteGroupRequest) -> PlatformGroupResponse:
    try:
        group = await add_platform_group(group_id=body.group_id, group_name=body.group_name, invited_by=user_id)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Group already has platform access") from exc
    return PlatformGroupResponse(
        group_id=group.group_id, group_name=group.group_name, invited_by=group.invited_by, created_at=group.created_at
    )


@router.delete("/groups/{group_id}", status_code=204)
async def revoke_group(user_id: AdminDep, group_id: str) -> None:
    removed = await remove_platform_group(group_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Group not found")
