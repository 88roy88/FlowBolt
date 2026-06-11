"""REST endpoints for project CRUD."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from flow44.api.deps import Permission, PlatformUserDep, ProjectDep, UserDep, is_admin, require_permission
from flow44.auth.permissions import get_admin_permissions, has_permission
from flow44.db.platform_user import is_platform_user as db_is_platform_user
from flow44.db.project import (
    create_project,
    delete_project,
    list_all_projects,
    rename_project,
    update_project_model,
)
from flow44.db.project import list_user_projects as db_list_user_projects
from flow44.db.project_member import list_shared_projects
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


@router.get("/me")
async def get_current_user(user_id: UserDep) -> dict[str, Any]:
    admin = is_admin(user_id)
    return {
        "user_id": user_id,
        "is_admin": admin,
        "is_platform_user": admin or await db_is_platform_user(user_id),
    }


@router.get("")
async def list_user_projects(user_id: UserDep) -> list[dict[str, Any]]:
    user_perms = get_admin_permissions() if is_admin(user_id) else set()
    can_read_all = has_permission(user_perms, Permission.read)

    if can_read_all:
        all_projects = await list_all_projects()
        result: list[dict[str, Any]] = []
        for p in all_projects:
            role = "owner" if p.user_id == user_id else "admin"
            result.append(p.model_dump() | {"role": role})
        return result

    owned = await db_list_user_projects(user_id)
    shared = await list_shared_projects(user_id)

    result = []
    for p in owned:
        result.append(p.model_dump() | {"role": "owner"})
    for p, role in shared:
        result.append(p.model_dump() | {"role": role})

    return result


@router.post("", status_code=201)
async def create_new_project(body: CreateProjectRequest, user_id: PlatformUserDep) -> dict[str, Any]:
    project = await create_project(body.name, user_id)

    async def _create() -> None:
        from flow44.db.events import emit_event  # noqa: PLC0415

        try:
            await sandbox_manager.create_sandbox(project.id)
        except Exception:
            logger.exception("[projects] Sandbox creation failed for project %s", project.id)
            await emit_event(project.id, {"type": "error", "message": "Project setup failed"})

    asyncio.create_task(_create())
    return project.model_dump()


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
