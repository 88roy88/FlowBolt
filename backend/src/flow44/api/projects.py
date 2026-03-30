"""REST endpoints for project CRUD."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.config import settings
from flow44.db.project import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    rename_project,
    update_project_model,
)
from flow44.db.session import project_registry
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
async def list_all_projects() -> list[dict[str, Any]]:
    projects = await list_projects()
    return [p.model_dump() for p in projects]


@router.post("", status_code=201)
async def create_new_project(body: CreateProjectRequest) -> dict[str, Any]:
    project = await create_project(body.name)

    sandbox = await sandbox_manager.create_sandbox(project.id)
    project_registry.register(project.id, sandbox.info)

    async def _scaffold_and_start() -> None:
        from flow44.db.events import emit_event  # noqa: PLC0415

        try:
            logger.info("[projects] Scaffolding project for session %s", project.id)
            await sandbox.scaffold(settings.TEMPLATE_DIR)
            logger.info("[projects] Starting dev server for session %s", project.id)
            await sandbox.start_dev_server()
        except Exception:
            logger.exception("[projects] Scaffolding failed for session %s", project.id)
            await emit_event(project.id, {"type": "error", "message": "Project setup failed"})

    # TODO: shouldnt we use the fastapi background-task for this?
    asyncio.create_task(_scaffold_and_start())
    return project.model_dump()


@router.patch("/{project_id}/name", status_code=200)
async def rename_existing_project(project_id: str, body: RenameProjectRequest) -> dict[str, bool]:
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    await rename_project(project_id, body.name.strip())
    return {"success": True}


@router.patch("/{project_id}/model", status_code=200)
async def update_project_selected_model(project_id: str, body: UpdateProjectModelRequest) -> dict[str, bool]:
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await update_project_model(project_id, body.model)
    return {"success": True}


@router.delete("/{project_id}", status_code=204)
async def delete_existing_project(project_id: str) -> None:
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await sandbox_manager.destroy_sandbox(project.id, delete_workspace=True)
    project_registry.remove(project.id)
    await delete_project(project_id)
