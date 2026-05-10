from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import Depends, HTTPException, WebSocket

from flow44.api.auth import ProjectDep, extract_user_id, get_project, get_ws_project
from flow44.db.project import Project
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


async def read_auth_frame(websocket: WebSocket) -> dict[str, object] | None:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        data = json.loads(raw)
    except Exception:
        await websocket.close(code=1008, reason="Unauthorized")
        return None

    if not isinstance(data, dict) or data.get("type") != "auth":
        await websocket.close(code=1008, reason="Unauthorized")
        return None

    return data


async def _authorize_ws_project(websocket: WebSocket, project_id: str, auth_frame: dict[str, object]) -> Project | None:
    token = auth_frame.get("userAuthorization")
    try:
        user_id = extract_user_id(token if isinstance(token, str) else None)
        return await get_project(project_id, user_id)
    except HTTPException:
        await websocket.close(code=1008, reason="Unauthorized")
        return None


async def _resolve_ws_sandbox(websocket: WebSocket, project_id: str) -> PnpmSandbox | None:
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        await websocket.close(code=1008, reason="Sandbox not found")
        return None


async def accept_ws_sandbox(websocket: WebSocket, project_id: str) -> PnpmSandbox | None:
    """Accept WS, authenticate via first auth frame, return sandbox or None."""
    await websocket.accept()

    auth_frame = await read_auth_frame(websocket)
    if auth_frame is None:
        return None

    project = await _authorize_ws_project(websocket, project_id, auth_frame)
    if project is None:
        return None

    return await _resolve_ws_sandbox(websocket, project.id)
