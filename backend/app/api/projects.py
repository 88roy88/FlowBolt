"""REST endpoints for project CRUD."""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.project import create_project, delete_project, get_project, list_projects
from app.models.session import session_registry
from app.sandbox.manager import sandbox_manager
from app.sandbox.nsjail import exec_in_sandbox

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str


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
    sandbox_info = await sandbox_manager.create_sandbox(project.session_id)

    # Register session
    session_registry.register(project.session_id, project.id, sandbox_info)

    # Scaffold a React + Vite + TypeScript project
    logger.info("[projects] Scaffolding React project for session %s", project.session_id)
    scaffold_output: list[str] = []
    try:
        async for line in exec_in_sandbox(
            project.session_id,
            "pnpm create vite . --template react-ts -- --yes 2>&1 && pnpm install 2>&1",
        ):
            scaffold_output.append(line)
            logger.info("[scaffold] %s", line.rstrip())
    except Exception:
        logger.exception("[projects] Scaffold failed for session %s", project.session_id)

    # Start the dev server in the background
    logger.info("[projects] Starting dev server for session %s", project.session_id)
    await sandbox_manager.start_dev_server(project.session_id)

    return asdict(project)


@router.delete("/{project_id}", status_code=204)
async def delete_existing_project(project_id: str):
    """Delete a project and tear down its sandbox."""
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Destroy sandbox and delete workspace files
    await sandbox_manager.destroy_sandbox(project.session_id, delete_workspace=True)
    session_registry.remove(project.session_id)

    # Delete from database
    await delete_project(project_id)
