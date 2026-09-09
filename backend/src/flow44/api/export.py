"""REST endpoints for exporting project files."""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from flow44.api.deps import ProjectDep, SandboxDep
from flow44.sandbox.operations import BuildError, build_single_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{project_id}", tags=["export"])

EXCLUDED_DIRS = {"node_modules", ".git", "dist", ".cache"}


def _attachment(filename: str) -> str:
    ascii_fallback = re.sub(r"[^A-Za-z0-9\-. ]", "_", filename).strip("_ ")
    if not ascii_fallback or ascii_fallback.startswith("."):
        ascii_fallback = f"export{ascii_fallback}"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _download_response(content: bytes | str, filename: str, media_type: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": _attachment(filename)},
    )


@router.get("/zip")
async def export_zip(project: ProjectDep, sandbox: SandboxDep) -> Response:
    """Download the entire project workspace as a ZIP file."""
    workspace_dir = sandbox.workspace_dir
    if not os.path.isdir(workspace_dir):  # noqa: ASYNC240
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    project_name = project.name

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(workspace_dir):
            # Filter out excluded directories in-place so os.walk skips them
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for filename in files:
                abs_path = os.path.join(root, filename)
                arc_name = os.path.relpath(abs_path, workspace_dir)  # noqa: ASYNC240
                try:
                    zf.write(abs_path, arc_name)
                except (PermissionError, OSError) as exc:
                    logger.warning("Skipping file %s: %s", arc_name, exc)

    return _download_response(buf.getvalue(), f"{project_name}.zip", "application/zip")


@router.get("/html")
async def export_html(project: ProjectDep) -> Response:
    """Build the project and return a single self-contained HTML file."""
    try:
        html = await build_single_html(project.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _download_response(html, f"{project.name}.html", "text/html")
