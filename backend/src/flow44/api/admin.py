import asyncio
import os
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from flow44.api.deps import UserDep, is_admin
from flow44.config import settings
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
from flow44.db.project import Project, list_published_projects
from flow44.services.maintenance.runner import ProjectMaintenanceResult, run_over_projects
from flow44.services.maintenance.sandbox_file_permissions import fix_file_permissions
from flow44.services.maintenance.template_sync import sync_protected_template_files

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def require_admin(user_id: UserDep) -> str:
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


AdminDep = Annotated[str, Depends(require_admin)]


class InviteUserRequest(BaseModel):
    user_id: str
    display_name: str = ""


class PlatformUserResponse(BaseModel):
    user_id: str
    display_name: str
    invited_by: str
    created_at: datetime | None


class InviteGroupRequest(BaseModel):
    group_id: str  # AD distinguishedName (DN)
    group_name: str = ""
    email: str = ""


class PlatformGroupResponse(BaseModel):
    group_id: str
    group_name: str
    email: str
    invited_by: str
    created_at: datetime | None


class PublishedAppResponse(BaseModel):
    project_id: str
    name: str
    owner_id: str
    project_url: str  # projects.published_url — the slug, or the project id if none was chosen
    public_path: str
    published_at: str


@router.get("/users")
async def list_users(user_id: AdminDep) -> list[PlatformUserResponse]:
    users = await list_platform_users()
    return [
        PlatformUserResponse(
            user_id=u.user_id, display_name=u.display_name, invited_by=u.invited_by, created_at=u.created_at
        )
        for u in users
    ]


@router.post("/users", status_code=201)
async def invite_user(user_id: AdminDep, body: InviteUserRequest) -> PlatformUserResponse:
    try:
        user = await add_platform_user(user_id=body.user_id, invited_by=user_id, display_name=body.display_name)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="User already has platform access") from exc
    return PlatformUserResponse(
        user_id=user.user_id, display_name=user.display_name, invited_by=user.invited_by, created_at=user.created_at
    )


@router.get("/published-apps")
async def list_published_apps(user_id: AdminDep) -> list[PublishedAppResponse]:
    """List every published project across the platform."""
    projects = await list_published_projects()
    return [
        PublishedAppResponse(
            project_id=p.id,
            name=p.name,
            owner_id=p.user_id,
            project_url=handle,
            public_path=f"/shared/{handle}",
            published_at=published_at,
        )
        # published_url/published_at are non-null for every row the query returns;
        # the walrus bindings narrow them for the type checker.
        for p in projects
        if (handle := p.published_url) is not None and (published_at := p.published_at) is not None
    ]


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
            group_id=g.group_id,
            group_name=g.group_name,
            email=g.email,
            invited_by=g.invited_by,
            created_at=g.created_at,
        )
        for g in groups
    ]


@router.post("/groups", status_code=201)
async def invite_group(user_id: AdminDep, body: InviteGroupRequest) -> PlatformGroupResponse:
    try:
        group = await add_platform_group(
            group_id=body.group_id, group_name=body.group_name, invited_by=user_id, email=body.email
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Group already has platform access") from exc
    return PlatformGroupResponse(
        group_id=group.group_id,
        group_name=group.group_name,
        email=group.email,
        invited_by=group.invited_by,
        created_at=group.created_at,
    )


@router.delete("/groups/{group_id}", status_code=204)
async def revoke_group(user_id: AdminDep, group_id: str) -> None:
    removed = await remove_platform_group(group_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Group not found")


@router.post("/maintenance/fix-file-permissions", tags=["maintenance"])
async def fix_workspace_file_permissions(user_id: AdminDep) -> list[ProjectMaintenanceResult]:
    """Make all workspace files world-writable. (new files will be world-writable already after os.umask(0))"""

    async def fix_permissions(project: Project) -> str:
        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, project.id)
        return await asyncio.to_thread(fix_file_permissions, workspace_dir)

    return await run_over_projects(fix_permissions)


@router.post("/maintenance/sync-protected-files", tags=["maintenance"])
async def sync_protected_files(user_id: AdminDep) -> list[ProjectMaintenanceResult]:
    """Overwrite each project's template files with the up-to-date template if they differ."""

    async def sync_files(project: Project) -> str:
        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, project.id)
        return await asyncio.to_thread(sync_protected_template_files, workspace_dir, settings.TEMPLATE_DIR)

    return await run_over_projects(sync_files)
