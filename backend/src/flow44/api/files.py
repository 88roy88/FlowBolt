from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from flow44.api.deps import SandboxDep
from flow44.sandbox.main import PnpmSandbox

router = APIRouter(prefix="/api/files/{project_id}", tags=["files"])


class WriteFileRequest(BaseModel):
    path: str
    content: str


class CreateFileRequest(BaseModel):
    path: str
    content: str = ""


class RenamePathRequest(BaseModel):
    old_path: str
    new_path: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    case_sensitive: bool = False
    word_match: bool = False
    use_regex: bool = False
    max_results: int = Field(default=500, ge=1, le=2000)


class SearchHit(BaseModel):
    line: int = Field(ge=1, description="Line number (1-indexed)")
    column: int = Field(ge=1, description="Column number (1-indexed)")
    preview: str = Field(description="Preview of the line containing the match")


class SearchResultFile(BaseModel):
    path: str = Field(description="File path (workspace-relative, starts with /)")
    uri: str = Field(description="File URI for Monaco editor")
    hits: list[SearchHit] = Field(description="All matches found in this file")


class SearchResponse(BaseModel):
    query: str = Field(description="The search query that was executed")
    results: list[SearchResultFile] = Field(description="Results grouped by file")


@router.get("/tree")
async def get_file_tree(sandbox: Annotated[PnpmSandbox, SandboxDep]) -> list[dict[str, Any]]:
    try:
        tree = await sandbox.list_files()
        return [entry.model_dump() for entry in tree]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/content")
async def get_file_content(sandbox: Annotated[PnpmSandbox, SandboxDep], path: str = Query(...)) -> dict[str, str]:
    try:
        content = await sandbox.read_file(path)
        return {"path": path, "content": content}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.put("/content")
async def put_file_content(sandbox: Annotated[PnpmSandbox, SandboxDep], body: WriteFileRequest) -> dict[str, str]:
    try:
        await sandbox.write_file(body.path, body.content)
        return {"status": "ok", "path": body.path}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.post("/entry")
async def post_create_file(sandbox: Annotated[PnpmSandbox, SandboxDep], body: CreateFileRequest) -> dict[str, str]:
    try:
        await sandbox.create_file(body.path, body.content)
        return {"status": "ok", "path": body.path}
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.patch("/entry")
async def patch_rename_path(sandbox: Annotated[PnpmSandbox, SandboxDep], body: RenamePathRequest) -> dict[str, str]:
    try:
        await sandbox.rename_path(body.old_path, body.new_path)
        return {"status": "ok", "old_path": body.old_path, "new_path": body.new_path}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.delete("/entry")
async def delete_entry(sandbox: Annotated[PnpmSandbox, SandboxDep], path: str = Query(...)) -> dict[str, str]:
    try:
        await sandbox.delete_file(path)
        return {"status": "ok", "path": path}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except OSError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.get("/grep")
async def get_grep(
    sandbox: Annotated[PnpmSandbox, SandboxDep],
    pattern: str = Query(...),
    path: str = Query(default="/"),
    file_pattern: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        matches = await sandbox.grep(pattern, path, file_pattern)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    return {"matches": [{"file": m.file, "line": m.line, "content": m.content} for m in matches]}


@router.post("/search")
async def post_search(sandbox: Annotated[PnpmSandbox, SandboxDep], body: SearchRequest) -> SearchResponse:
    """Search using ripgrep with column positions for frontend integration."""
    try:
        # Use grep with column tracking
        # Build pattern based on options
        pattern = body.query
        if not body.case_sensitive and body.use_regex:
            # For regex mode, use (?i) flag for case-insensitive
            pattern = f"(?i){pattern}"

        matches = await sandbox.grep(
            pattern=pattern,
            path="/",
            file_pattern=None,
            max_results=body.max_results,
            with_column=True,
            case_sensitive=body.case_sensitive,
            word_match=body.word_match,
            fixed_strings=not body.use_regex,  # Use literal search when regex is off
        )

        # Group matches by file
        files_dict: dict[str, list[SearchHit]] = {}
        for m in matches:
            if m.file not in files_dict:
                files_dict[m.file] = []
            files_dict[m.file].append(
                SearchHit(
                    line=m.line,
                    column=m.column or 1,  # Default to column 1 if not available
                    preview=m.content.strip()[:200],  # Limit preview length
                )
            )

        return SearchResponse(
            query=body.query,
            results=[SearchResultFile(path=file, uri=f"file://{file}", hits=hits) for file, hits in files_dict.items()],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
