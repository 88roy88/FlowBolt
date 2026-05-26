"""REST endpoints for exporting project files."""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from flow44.api.deps import SandboxDep
from flow44.db.project import get_project
from flow44.paths import EXPORT_API_PREFIX
from flow44.sandbox.main import PnpmSandbox
from flow44.sandbox.operations import BuildError, build_single_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{EXPORT_API_PREFIX}/{{project_id}}", tags=["export"])

EXCLUDED_DIRS = {"node_modules", ".git", "dist", ".cache"}


@router.get("/zip")
async def export_zip(project_id: str, sandbox: Annotated[PnpmSandbox, SandboxDep]) -> Response:
    """Download the entire project workspace as a ZIP file."""
    workspace_dir = sandbox.workspace_dir
    if not os.path.isdir(workspace_dir):  # noqa: ASYNC240
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    project = await get_project(project_id)
    project_name = project.name if project else project_id

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

    content = buf.getvalue()

    safe_name = re.sub(r"[^\w\-. ]", "_", project_name)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
    )


@router.get("/html")
async def export_html(project_id: str) -> Response:
    """Build the project and return a single self-contained HTML file."""
    try:
        html = await build_single_html(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    project = await get_project(project_id)
    project_name = project.name if project else project_id
    safe_name = re.sub(r"[^\w\-. ]", "_", project_name)

    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.html"'},
    )
