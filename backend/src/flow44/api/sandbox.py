from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, WebSocket

from flow44.api.auth import ProjectDep, get_ws_project
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager


async def get_sandbox(project: ProjectDep) -> PnpmSandbox:
    try:
        return sandbox_manager.get_sandbox(project.id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project.id}") from None


SandboxDep = Annotated[PnpmSandbox, Depends(get_sandbox)]


async def get_ws_sandbox(websocket: WebSocket, project_id: str) -> PnpmSandbox | None:
    """Convenience for WebSockets to get sandbox while enforcing ownership via query token."""
    project = await get_ws_project(websocket, project_id)
    if project is None:
        return None

    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        await websocket.close(code=1008, reason="Sandbox not found")
        return None
