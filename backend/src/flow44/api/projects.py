"""REST endpoints for project CRUD."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.api.deps import ProjectDep, UserDep
from flow44.db.project import (
    create_project,
    delete_project,
    rename_project,
    update_project_model,
)
from flow44.db.project import list_user_projects as db_list_user_projects
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


@router.get("")
async def list_user_projects(user_id: UserDep) -> list[dict[str, Any]]:
    projects = await db_list_user_projects(user_id)
    return [p.model_dump() for p in projects]


@router.post("", status_code=201)
async def create_new_project(body: CreateProjectRequest, user_id: UserDep) -> dict[str, Any]:
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
async def rename_existing_project(project: ProjectDep, body: RenameProjectRequest) -> dict[str, bool]:
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    await rename_project(project.id, body.name.strip())
    return {"success": True}


@router.patch("/{project_id}/model", status_code=200)
async def update_project_selected_model(project: ProjectDep, body: UpdateProjectModelRequest) -> dict[str, bool]:
    await update_project_model(project.id, body.model)
    return {"success": True}


@router.delete("/{project_id}", status_code=204)
async def delete_existing_project(project: ProjectDep) -> None:
    await sandbox_manager.destroy_sandbox(project.id)
    idle_reaper.remove(project.id)
    await delete_project(project.id)


@router.post("/{project_id}/debug/reap", status_code=200)
async def debug_reap_sandbox(project_id: str) -> dict[str, str]:
    """DEBUG: Force-evict a sandbox as if the idle reaper triggered."""
    if project_id not in sandbox_manager._sandboxes:
        raise HTTPException(status_code=404, detail="No active sandbox for this project")

    await sandbox_manager.suspend_sandbox(project_id)
    idle_reaper.remove(project_id)
    return {"status": "reaped", "project_id": project_id}


@router.get("/debug/sandboxes", status_code=200)
async def debug_list_sandboxes() -> dict[str, Any]:
    """DEBUG: Show active sandbox count and which projects have live sandboxes."""
    active = list(sandbox_manager._sandboxes.keys())
    return {"count": len(active), "project_ids": active}
