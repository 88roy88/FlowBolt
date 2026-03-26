from fastapi import Depends, HTTPException, WebSocket

from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.manager import SandboxNotFoundError, sandbox_manager


def get_sandbox(project_id: str) -> PnpmSandbox:
    """HTTP dependency: resolves sandbox from path param, raises 404 if not found."""
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project_id}") from None


async def get_ws_sandbox(websocket: WebSocket, project_id: str) -> PnpmSandbox | None:
    """WebSocket helper: returns sandbox or closes socket with 1008 and returns None."""
    try:
        return sandbox_manager.get_sandbox(project_id)
    except SandboxNotFoundError:
        await websocket.close(code=1008, reason="No sandbox")
        return None


SandboxDep = Depends(get_sandbox)
