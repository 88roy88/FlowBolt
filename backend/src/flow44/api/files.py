"""REST endpoints for sandbox file operations."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from flow44.sandbox.filesystem import list_files, read_file, write_file
from flow44.sandbox.search import search_across_files

router = APIRouter(prefix="/api/files/{project_id}", tags=["files"])


class WriteFileRequest(BaseModel):
    path: str
    content: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    case_sensitive: bool = False
    max_results: int = Field(default=2000, ge=1, le=5000)
    max_hits_per_file: int = Field(default=200, ge=1, le=500)


@router.get("/tree")
async def get_file_tree(project_id: str) -> list[dict[str, Any]]:
    try:
        tree = await list_files(project_id)
        return [asdict(entry) for entry in tree]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/content")
async def get_file_content(project_id: str, path: str = Query(...)) -> dict[str, str]:
    try:
        content = await read_file(project_id, path)
        return {"path": path, "content": content}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.put("/content")
async def put_file_content(project_id: str, body: WriteFileRequest) -> dict[str, str]:
    try:
        await write_file(project_id, body.path, body.content)
        return {"status": "ok", "path": body.path}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.post("/search")
async def post_search(project_id: str, body: SearchRequest) -> dict[str, Any]:
    try:
        results = await search_across_files(
            project_id,
            body.query,
            case_sensitive=body.case_sensitive,
            max_results=body.max_results,
            max_hits_per_file=body.max_hits_per_file,
        )
        return {"query": body.query, "results": results}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
