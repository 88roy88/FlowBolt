"""REST endpoints for project CRUD."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from flow44.config import settings
from flow44.models.project import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    rename_project,
    update_project_model,
)
from flow44.models.session import session_registry
from flow44.sandbox.manager import sandbox_manager, stamp_vite_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str


class RenameProjectRequest(BaseModel):
    name: str


class UpdateProjectModelRequest(BaseModel):
    model: str


@router.get("")
async def list_all_projects():
    """Return all projects."""
    projects = await list_projects()
    return [asdict(p) for p in projects]


@router.post("", status_code=201)
async def create_new_project(body: CreateProjectRequest):
    """Create a project, spin up a sandbox, and return the project with session_id."""
    project = await create_project(body.name)

    # Create sandbox for this project
    sandbox = await sandbox_manager.create_sandbox(project.session_id)

    # Register session
    session_registry.register(project.session_id, project.id, sandbox.info)

    # Scaffold + start dev server in the background (don't block response)
    async def _scaffold_and_start():
        logger.info("[projects] Scaffolding project for session %s", project.session_id)

        # Step 1: Copy template into workspace
        shutil.copytree(settings.TEMPLATE_DIR, sandbox.workspace_dir, dirs_exist_ok=True)

        # Step 2: Stamp session ID into vite config
        stamp_vite_config(project.session_id, sandbox.workspace_dir)

        # Step 3: Install dependencies (lockfile is already in the template)
        try:
            async for line in sandbox.exec("pnpm install 2>&1"):
                logger.info("[scaffold] %s", line.rstrip())
        except Exception:
            logger.exception("[projects] pnpm install failed for session %s", project.session_id)
            return

        # Step 4: Start dev server
        logger.info("[projects] Starting dev server for session %s", project.session_id)
        await sandbox.start_dev_server()

    asyncio.create_task(_scaffold_and_start())

    return asdict(project)


@router.patch("/{project_id}/name", status_code=200)
async def rename_existing_project(project_id: str, body: RenameProjectRequest):
    """Rename a project."""
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    await rename_project(project_id, body.name.strip())
    return {"success": True}


@router.patch("/{project_id}/model", status_code=200)
async def update_project_selected_model(project_id: str, body: UpdateProjectModelRequest):
    """Update the selected model for a project."""
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    await update_project_model(project_id, body.model)
    return {"success": True}


@router.delete("/{project_id}", status_code=204)
async def delete_existing_project(project_id: str):
    """Delete a project and tear down its sandbox."""
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Destroy sandbox (kills dev server + PTYs + deletes workspace)
    await sandbox_manager.destroy_sandbox(project.session_id, delete_workspace=True)
    session_registry.remove(project.session_id)

    # Delete from database
    await delete_project(project_id)
