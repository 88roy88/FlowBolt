"""REST endpoints for exporting project files."""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.project import get_project_by_session
from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{session_id}", tags=["export"])

EXCLUDED_DIRS = {"node_modules", ".git", "dist", ".cache"}


@router.get("/zip")
async def export_zip(session_id: str):
    """Download the entire project workspace as a ZIP file."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for session {session_id}")

    workspace_dir = sandbox.workspace_dir
    if not os.path.isdir(workspace_dir):
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    project = await get_project_by_session(session_id)
    project_name = project.name if project else session_id

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(workspace_dir):
            # Filter out excluded directories in-place so os.walk skips them
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for filename in files:
                abs_path = os.path.join(root, filename)
                arc_name = os.path.relpath(abs_path, workspace_dir)
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
async def export_html(session_id: str):
    """Build the project and return a single self-contained HTML file."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for session {session_id}")

    workspace_dir = sandbox.workspace_dir

    # Build with base=/ so assets use relative paths (not the preview proxy path)
    build_output_lines: list[str] = []
    async for line in sandbox.exec("VITE_BASE=/ pnpm build"):
        build_output_lines.append(line)
    build_output = "".join(build_output_lines)

    dist_dir = os.path.join(workspace_dir, "dist")
    index_path = os.path.join(dist_dir, "index.html")

    if not os.path.isfile(index_path):
        raise HTTPException(
            status_code=500,
            detail=f"Build failed or dist/index.html not found.\n\n{build_output}",
        )

    with open(index_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    # Inline CSS: <link rel="stylesheet" href="...">
    def inline_css(match: re.Match) -> str:
        href = match.group(1)
        css_path = _resolve_asset_path(dist_dir, href)
        if css_path and os.path.isfile(css_path):
            try:
                with open(css_path, "r", encoding="utf-8", errors="replace") as cf:
                    css_content = cf.read()
                return f"<style>{css_content}</style>"
            except OSError:
                pass
        return match.group(0)

    html = re.sub(
        r'<link\s+[^>]*rel=["\']stylesheet["\']\s+[^>]*href=["\']([^"\']+)["\'][^>]*/?>',
        inline_css,
        html,
        flags=re.IGNORECASE,
    )
    # Also handle href before rel
    html = re.sub(
        r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\'][^>]*/?>',
        inline_css,
        html,
        flags=re.IGNORECASE,
    )

    # Inline JS: <script src="...">
    def inline_js(match: re.Match) -> str:
        src = match.group(1)
        js_path = _resolve_asset_path(dist_dir, src)
        if js_path and os.path.isfile(js_path):
            try:
                with open(js_path, "r", encoding="utf-8", errors="replace") as jf:
                    js_content = jf.read()
                # Preserve type attribute if present (e.g. type="module")
                type_match = re.search(r'type=["\']([^"\']+)["\']', match.group(0))
                type_attr = f' type="{type_match.group(1)}"' if type_match else ""
                return f"<script{type_attr}>{js_content}</script>"
            except OSError:
                pass
        return match.group(0)

    html = re.sub(
        r'<script\s+[^>]*src=["\']([^"\']+)["\'][^>]*>\s*</script>',
        inline_js,
        html,
        flags=re.IGNORECASE,
    )

    project = await get_project_by_session(session_id)
    project_name = project.name if project else session_id
    safe_name = re.sub(r"[^\w\-. ]", "_", project_name)

    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.html"'},
    )


def _resolve_asset_path(dist_dir: str, href: str) -> str | None:
    """Resolve an asset href (possibly relative or absolute) to a filesystem path."""
    # Strip leading slash for absolute paths
    cleaned = href.lstrip("/")
    candidate = os.path.join(dist_dir, cleaned)
    # Prevent directory traversal
    if not os.path.realpath(candidate).startswith(os.path.realpath(dist_dir)):
        return None
    return candidate
