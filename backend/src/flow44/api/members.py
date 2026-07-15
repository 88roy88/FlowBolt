from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from flow44.api.deps import Permission, ProjectDep, UserDep, require_permission
from flow44.auth.permissions import Role
from flow44.db.project_member import (
    add_member,
    list_project_members,
    remove_member,
    update_member_role,
)
from flow44.db.project_member_group import (
    add_group,
    list_project_groups,
    remove_group,
    update_group_role,
)

router = APIRouter(prefix="/api/projects/{project_id}/members", tags=["members"])


class AddMemberRequest(BaseModel):
    user_id: str
    role: Role = Role.viewer


class UpdateMemberRoleRequest(BaseModel):
    role: Role


class MemberResponse(BaseModel):
    user_id: str
    role: str
    created_at: str
    invited_by: str


class AddGroupRequest(BaseModel):
    group_id: str  # AD objectGUID
    group_name: str = ""
    role: Role = Role.viewer


class UpdateGroupRoleRequest(BaseModel):
    role: Role


class GroupMemberResponse(BaseModel):
    group_id: str
    group_name: str
    role: str
    created_at: str
    invited_by: str


@router.get("")
async def list_members(
    project: ProjectDep,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> list[MemberResponse]:
    members = await list_project_members(project.id)
    return [
        MemberResponse(user_id=m.user_id, role=m.role, created_at=m.created_at, invited_by=m.invited_by)
        for m in members
    ]


@router.post("", status_code=201)
async def add_project_member(
    project: ProjectDep,
    body: AddMemberRequest,
    user_id: UserDep,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> MemberResponse:
    if body.user_id == project.user_id:
        raise HTTPException(status_code=400, detail="Cannot add the project owner as a member")

    try:
        member = await add_member(
            project_id=project.id,
            user_id=body.user_id,
            role=body.role,
            invited_by=user_id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="User is already a member of this project") from exc
    return MemberResponse(
        user_id=member.user_id, role=member.role, created_at=member.created_at, invited_by=member.invited_by
    )


@router.patch("/{target_user_id}")
async def update_member(
    project: ProjectDep,
    target_user_id: str,
    body: UpdateMemberRoleRequest,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> MemberResponse:
    member = await update_member_role(project.id, target_user_id, body.role)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return MemberResponse(
        user_id=member.user_id, role=member.role, created_at=member.created_at, invited_by=member.invited_by
    )


@router.delete("/{target_user_id}", status_code=204)
async def remove_project_member(
    project: ProjectDep,
    target_user_id: str,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> None:
    removed = await remove_member(project.id, target_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")


# --- Group grants (share a project with a directory group) ---


@router.get("/groups")
async def list_group_grants(
    project: ProjectDep,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> list[GroupMemberResponse]:
    grants = await list_project_groups(project.id)
    return [
        GroupMemberResponse(
            group_id=g.group_id,
            group_name=g.group_name,
            role=g.role,
            created_at=g.created_at,
            invited_by=g.invited_by,
        )
        for g in grants
    ]


@router.post("/groups", status_code=201)
async def add_group_grant(
    project: ProjectDep,
    body: AddGroupRequest,
    user_id: UserDep,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> GroupMemberResponse:
    try:
        grant = await add_group(
            project_id=project.id,
            group_id=body.group_id,
            group_name=body.group_name,
            role=body.role,
            invited_by=user_id,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Group already has access to this project") from exc
    return GroupMemberResponse(
        group_id=grant.group_id,
        group_name=grant.group_name,
        role=grant.role,
        created_at=grant.created_at,
        invited_by=grant.invited_by,
    )


@router.patch("/groups/{group_id}")
async def update_group_grant(
    project: ProjectDep,
    group_id: str,
    body: UpdateGroupRoleRequest,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> GroupMemberResponse:
    grant = await update_group_role(project.id, group_id, body.role)
    if grant is None:
        raise HTTPException(status_code=404, detail="Group grant not found")
    return GroupMemberResponse(
        group_id=grant.group_id,
        group_name=grant.group_name,
        role=grant.role,
        created_at=grant.created_at,
        invited_by=grant.invited_by,
    )


@router.delete("/groups/{group_id}", status_code=204)
async def remove_group_grant(
    project: ProjectDep,
    group_id: str,
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> None:
    removed = await remove_group(project.id, group_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Group grant not found")
