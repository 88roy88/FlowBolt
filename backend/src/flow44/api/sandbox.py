from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, WebSocketException

from flow44.api.auth import ProjectDep, WsProjectDep
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager

WS_SANDBOX_NOT_FOUND = 4404


async def get_sandbox(project: ProjectDep) -> PnpmSandbox:
    try:
        return sandbox_manager.get_sandbox(project.id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project.id}") from None


SandboxDep = Annotated[PnpmSandbox, Depends(get_sandbox)]


async def get_ws_sandbox(project: WsProjectDep) -> PnpmSandbox:
    try:
        return sandbox_manager.get_sandbox(project.id)
    except SandboxNotFoundError:
        raise WebSocketException(code=WS_SANDBOX_NOT_FOUND, reason="Sandbox not found") from None


WsSandboxDep = Annotated[PnpmSandbox, Depends(get_ws_sandbox)]
