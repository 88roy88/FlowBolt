"""Preview management endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.sandbox.manager import sandbox_manager

router = APIRouter(prefix="/api/preview", tags=["preview"])


@router.get("/{session_id}/port")
async def get_preview_port(session_id: str):
    """Return the allocated port for the sandbox's dev server.

    Useful for nginx proxy configuration or direct browser access.
    """
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail="No sandbox found for this session")

    return {"session_id": session_id, "port": sandbox.port}
