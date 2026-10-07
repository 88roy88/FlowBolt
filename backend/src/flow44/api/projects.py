"""REST endpoints for project CRUD."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from flow44.api.deps import Permission, PlatformUserDep, ProjectDep, UserDep, is_admin, require_permission
from flow44.auth.permissions import Role, get_admin_permissions, has_permission
from flow44.db.platform_user import is_platform_user as db_is_platform_user
from flow44.db.project import (
    Project,
    create_project,
    delete_project,
    rename_project,
    update_project_model,
)
from flow44.db.project_member import get_project_member, list_accessible_projects
from flow44.integrations.s3 import s3_storage
from flow44.sandbox.idle_reaper import idle_reaper
from flow44.sandbox.manager import sandbox_manager
from flow44.services.versioning import service as versioning

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


@router.get("/me")
async def get_current_user(user_id: UserDep) -> dict[str, Any]:
    admin = is_admin(user_id)
    return {
        "user_id": user_id,
        "is_admin": admin,
        "is_platform_user": admin or await db_is_platform_user(user_id),
    }


def _encode_cursor(project: Project) -> str:
    return base64.urlsafe_b64encode(json.dumps([project.created_at, project.id]).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        created_at, project_id = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid cursor") from None
    if not isinstance(created_at, str) or not isinstance(project_id, str):
        raise HTTPException(status_code=400, detail="Invalid cursor")
    return created_at, project_id


def _role_for(project: Project, user_id: str, member_role: Role | None) -> str:
    if project.user_id == user_id:
        return "owner"
    if is_admin(user_id) or member_role is None:
        return "admin"
    return member_role.value


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    next_cursor: str | None


@router.get("")
async def list_user_projects(
    user_id: UserDep,
    q: Annotated[str, Query(max_length=200)] = "",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ProjectListResponse:
    user_perms = get_admin_permissions() if is_admin(user_id) else set()
    rows = await list_accessible_projects(
        user_id,
        include_all=has_permission(user_perms, Permission.read),
        name_query=q.strip(),
        before=_decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    page = rows[:limit]
    return ProjectListResponse(
        projects=[_serialize_project(p, _role_for(p, user_id, role)) for p, role in page],
        next_cursor=_encode_cursor(page[-1][0]) if len(rows) > limit else None,
    )


@router.get("/{project_id}")
async def get_single_project(project: ProjectDep, user_id: UserDep) -> ProjectResponse:
    member = None if project.user_id == user_id or is_admin(user_id) else await get_project_member(project.id, user_id)
    return _serialize_project(project, _role_for(project, user_id, Role(member.role) if member else None))


@router.post("", status_code=201)
async def create_new_project(body: CreateProjectRequest, user_id: PlatformUserDep) -> ProjectResponse:
    project = await create_project(body.name, user_id)

    async def _create() -> None:
        from flow44.db.events import emit_event  # noqa: PLC0415

        try:
            await sandbox_manager.create_sandbox(project.id)
            await versioning.ensure_repo(project.id)
        except Exception:
            logger.exception("[projects] Sandbox creation failed for project %s", project.id)
            await emit_event(project.id, {"type": "error", "message": "Project setup failed"})

    asyncio.create_task(_create())
    return _serialize_project(project, "owner")


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
    await s3_storage.delete_published_prefix(project.id)
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
