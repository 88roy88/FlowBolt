"""REST endpoints for sandbox file operations."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.sandbox.filesystem import list_files, read_file, write_file

router = APIRouter(prefix="/api/files/{session_id}", tags=["files"])


class WriteFileRequest(BaseModel):
    path: str
    content: str


@router.get("/tree")
async def get_file_tree(session_id: str):
    """Return a recursive file tree for the sandbox workspace."""
    try:
        tree = await list_files(session_id)
        return [asdict(entry) for entry in tree]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/content")
async def get_file_content(session_id: str, path: str = Query(...)):
    """Return the text content of a file inside the sandbox."""
    try:
        content = await read_file(session_id, path)
        return {"path": path, "content": content}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.put("/content")
async def put_file_content(session_id: str, body: WriteFileRequest):
    """Write content to a file inside the sandbox."""
    try:
        await write_file(session_id, body.path, body.content)
        return {"status": "ok", "path": body.path}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
