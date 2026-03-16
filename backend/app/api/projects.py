"""REST endpoints for project CRUD."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.project import create_project, delete_project, get_project, list_projects
from app.models.session import session_registry
from app.sandbox.manager import sandbox_manager

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

    return asdict(project)


@router.delete("/{project_id}", status_code=204)
async def delete_existing_project(project_id: str):
    """Delete a project and tear down its sandbox."""
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # Destroy sandbox
    await sandbox_manager.destroy_sandbox(project.session_id)
    session_registry.remove(project.session_id)

    # Delete from database
    await delete_project(project_id)
