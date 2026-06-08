from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.api.deps import Permission, ProjectDep, require_permission
from flow44.auth.permissions import Role
from flow44.db.project_member import (
    add_member,
    list_project_members,
    remove_member,
    update_member_role,
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
    _perms: set[Permission] = require_permission(Permission.manage_members),
) -> MemberResponse:
    if body.user_id == project.user_id:
        raise HTTPException(status_code=400, detail="Cannot add the project owner as a member")

    member = await add_member(
        project_id=project.id,
        user_id=body.user_id,
        role=body.role,
        invited_by=project.user_id,
    )
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
