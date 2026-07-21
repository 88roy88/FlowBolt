"""REST endpoints for project CRUD."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from flow44.api.deps import (
    Permission,
    PlatformUserDep,
    ProjectDep,
    UserDep,
    has_platform_access,
    is_admin,
    require_permission,
)
from flow44.auth.permissions import Role, get_admin_permissions, has_permission
from flow44.db.project import (
    Project,
    create_project,
    delete_project,
    list_all_projects,
    rename_project,
    update_project_model,
)
from flow44.db.project import list_user_projects as db_list_user_projects
from flow44.db.project_member import list_shared_projects
from flow44.db.project_member_group import list_group_shared_projects
from flow44.integrations.adapi.client import adapi_client
from flow44.integrations.s3 import s3_storage
from flow44.sandbox.idle_reaper import idle_reaper
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str


class RenameProjectRequest(BaseModel):
    name: str


class UpdateProjectModelRequest(BaseModel):
    model: str


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    created_at: str
    updated_at: str
    summary: str
    selected_model: str
    published_url: str | None = None
    published_at: str | None = None
    role: str


def _serialize_project(project: Project, role: str) -> ProjectResponse:
    return ProjectResponse.model_validate(project.model_dump(exclude={"data_sources"}) | {"role": role})


# Display-only role labels for the creator/admin tiers (no Role enum member).
_OWNER_ROLE = "owner"
_ADMIN_ROLE = "admin"

# Display precedence when a project reaches a user through several sources; higher
# wins. Cosmetic only — authorization unions permissions in deps.
_ROLE_RANK: dict[str, int] = {
    Role.viewer.value: 1,
    Role.editor.value: 2,
    Role.publisher.value: 2,
    Role.maintainer.value: 3,
    _ADMIN_ROLE: 4,
    _OWNER_ROLE: 5,
}


@router.get("/me")
async def get_current_user(user_id: UserDep) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "is_admin": is_admin(user_id),
        "is_platform_user": await has_platform_access(user_id),
    }


@router.get("")
async def list_user_projects(user_id: UserDep) -> list[ProjectResponse]:
    user_perms = get_admin_permissions() if is_admin(user_id) else set()
    can_read_all = has_permission(user_perms, Permission.read)

    if can_read_all:
        all_projects = await list_all_projects()
        result: list[ProjectResponse] = []
        for p in all_projects:
            role = _OWNER_ROLE if p.user_id == user_id else _ADMIN_ROLE
            result.append(_serialize_project(p, role))
        return result

    owned, shared, user_group_ids = await asyncio.gather(
        db_list_user_projects(user_id),
        list_shared_projects(user_id),
        adapi_client.get_user_group_ids(user_id),
    )
    group_shared = await list_group_shared_projects(user_group_ids)

    # Collapse to one entry per project, keeping the highest-ranked role for display.
    by_id: dict[str, tuple[Project, str]] = {}

    def _merge(project: Project, role: str) -> None:
        existing = by_id.get(project.id)
        if existing is None or _ROLE_RANK.get(role, 0) > _ROLE_RANK.get(existing[1], 0):
            by_id[project.id] = (project, role)

    for p in owned:
        _merge(p, _OWNER_ROLE)
    for p, role in shared:
        _merge(p, role.value)
    for p, role in group_shared:
        _merge(p, role.value)

    return [_serialize_project(p, role) for p, role in by_id.values()]


@router.post("", status_code=201)
async def create_new_project(body: CreateProjectRequest, user_id: PlatformUserDep) -> ProjectResponse:
    project = await create_project(body.name, user_id)

    async def _create() -> None:
        from flow44.db.events import emit_event  # noqa: PLC0415

        try:
            await sandbox_manager.create_sandbox(project.id)
        except Exception:
            logger.exception("[projects] Sandbox creation failed for project %s", project.id)
            await emit_event(project.id, {"type": "error", "message": "Project setup failed"})

    asyncio.create_task(_create())
    return _serialize_project(project, _OWNER_ROLE)


@router.patch("/{project_id}/name", status_code=200)
async def rename_existing_project(
    project: ProjectDep,
    body: RenameProjectRequest,
    _perms: set[Permission] = require_permission(Permission.write),
) -> dict[str, bool]:
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    await rename_project(project.id, body.name.strip())
    return {"success": True}


@router.patch("/{project_id}/model", status_code=200)
async def update_project_selected_model(
    project: ProjectDep,
    body: UpdateProjectModelRequest,
    _perms: set[Permission] = require_permission(Permission.write),
) -> dict[str, bool]:
    await update_project_model(project.id, body.model)
    return {"success": True}


@router.delete("/{project_id}", status_code=204)
async def delete_existing_project(
    project: ProjectDep,
    background_tasks: BackgroundTasks,
    _perms: set[Permission] = require_permission(Permission.delete),
) -> None:
    idle_reaper.remove(project.id)
    await s3_storage.delete_published_html(project.id)
    await delete_project(project.id)
    background_tasks.add_task(sandbox_manager.destroy_sandbox, project.id)


@router.post("/{project_id}/debug/reap", status_code=200)
async def debug_reap_sandbox(project_id: str) -> dict[str, str]:
    """DEBUG: Force-evict a sandbox as if the idle reaper triggered."""
    if not sandbox_manager.has_active_sandbox(project_id):
        return {"status": "already_sleeping", "project_id": project_id}

    await sandbox_manager.suspend_sandbox(project_id)
    idle_reaper.remove(project_id)
    return {"status": "reaped", "project_id": project_id}


@router.get("/debug/sandboxes", status_code=200)
async def debug_list_sandboxes() -> dict[str, Any]:
    """DEBUG: Show active sandbox count and which projects have live sandboxes."""
    active = sandbox_manager.active_project_ids()
    return {"count": len(active), "project_ids": active}
