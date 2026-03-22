"""REST endpoints for exporting project files."""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import zipfile
import httpx

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, HTMLResponse

from flow44.config import settings
from flow44.models.project import get_project_by_session
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export/{session_id}", tags=["export"])

EXCLUDED_DIRS = {"node_modules", ".git", "dist", ".cache"}


@router.get("/zip")
async def export_zip(session_id: str) -> Response:
    """Download the entire project workspace as a ZIP file."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for session {session_id}")

    workspace_dir = sandbox.workspace_dir
    if not os.path.isdir(workspace_dir):  # noqa: ASYNC240
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


async def build_single_html(session_id: str) -> str:
    """Build the project and return a single self-contained HTML string."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for session {session_id}")

    workspace_dir = sandbox.workspace_dir

    # Write a temporary .env.production.local so vite picks up overrides
    # during the build. This is cross-platform (no shell env prefix needed).
    # VITE_BASE=/ overrides the proxy base path so assets use root-relative URLs.
    # VITE_API_BASE sets the backend URL for runtime fetch() calls.
    api_base = settings.EXPORT_API_BASE_URL or "http://localhost:8000"
    env_file = os.path.join(workspace_dir, ".env.production.local")
    try:
        with open(env_file, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            f.write(f"VITE_BASE=/\nVITE_API_BASE={api_base}\n")

        build_output_lines: list[str] = []
        async for line in sandbox.exec("pnpm build"):
            build_output_lines.append(line)
        build_output = "".join(build_output_lines)
    finally:
        try:
            os.remove(env_file)
        except OSError:
            pass

    dist_dir = os.path.join(workspace_dir, "dist")
    index_path = os.path.join(dist_dir, "index.html")

    if not os.path.isfile(index_path):  # noqa: ASYNC240
        raise HTTPException(
            status_code=500,
            detail=f"Build failed or dist/index.html not found.\n\n{build_output}",
        )

    with open(index_path, encoding="utf-8", errors="replace") as f:  # noqa: ASYNC230
        html = f.read()

    # --- Inline CSS ---
    def inline_css(match: re.Match[str]) -> str:
        href = match.group(1)
        css_path = _resolve_asset_path(dist_dir, href)
        if css_path and os.path.isfile(css_path):
            try:
                with open(css_path, encoding="utf-8", errors="replace") as cf:
                    return f"<style>{cf.read()}</style>"
            except OSError:
                pass
        return match.group(0)

    # Handle both orderings: rel before href, and href before rel
    html = re.sub(
        r'<link\s[^>]*?href=["\']([^"\']+)["\'][^>]*?rel=["\']stylesheet["\'][^>]*/?>',
        inline_css,
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<link\s[^>]*?rel=["\']stylesheet["\'][^>]*?href=["\']([^"\']+)["\'][^>]*/?>',
        inline_css,
        html,
        flags=re.IGNORECASE,
    )

    # --- Inline JS ---
    def inline_js(match: re.Match[str]) -> str:
        src = match.group(1)
        js_path = _resolve_asset_path(dist_dir, src)
        if js_path and os.path.isfile(js_path):
            try:
                with open(js_path, encoding="utf-8", errors="replace") as jf:
                    js_content = jf.read()
                type_match = re.search(r'type=["\']([^"\']+)["\']', match.group(0))
                type_attr = f' type="{type_match.group(1)}"' if type_match else ""
                return f"<script{type_attr}>{js_content}</script>"
            except OSError:
                pass
        return match.group(0)

    html = re.sub(
        r'<script\s[^>]*?src=["\']([^"\']+)["\'][^>]*?>\s*</script>',
        inline_js,
        html,
        flags=re.IGNORECASE,
    )

    # --- Inline favicon as data URI ---
    html = _inline_favicon(html, dist_dir, workspace_dir)

    # --- Strip the error reporter script (only useful inside the builder iframe) ---
    html = re.sub(
        r'<script\s+id=["\']__ERROR_REPORTER__["\']>.*?</script>\s*',
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return html


@router.get("/html")
async def export_html(session_id: str):
    """Build the project and return a single self-contained HTML file."""
    html = await build_single_html(session_id)

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
    cleaned = href.lstrip("/")
    candidate = os.path.join(dist_dir, cleaned)
    if not os.path.realpath(candidate).startswith(os.path.realpath(dist_dir)):
        return None
    return candidate


def _inline_favicon(html: str, dist_dir: str, workspace_dir: str) -> str:
    """Replace favicon <link> with an inline data URI."""

    def replace_favicon(match: re.Match[str]) -> str:
        href = match.group(1)
        # Try dist first, then workspace root (dev favicons live in public/)
        for base in (dist_dir, os.path.join(workspace_dir, "public"), workspace_dir):
            path = os.path.join(base, href.lstrip("/"))
            if os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    if path.endswith(".svg"):
                        b64 = base64.b64encode(data).decode()
                        return f'<link rel="icon" href="data:image/svg+xml;base64,{b64}">'
                    ext = os.path.splitext(path)[1].lstrip(".")
                    mime = {"png": "image/png", "ico": "image/x-icon", "jpg": "image/jpeg"}.get(ext, "image/png")
                    b64 = base64.b64encode(data).decode()
                    return f'<link rel="icon" href="data:{mime};base64,{b64}">'
                except OSError:
                    pass
        return match.group(0)

    return re.sub(
        r'<link\s[^>]*?rel=["\'](?:icon|shortcut icon)["\'][^>]*?href=["\']([^"\']+)["\'][^>]*/?>',
        replace_favicon,
        html,
        flags=re.IGNORECASE,
    )


@router.get("/published", response_class=HTMLResponse)
async def proxy_published_app(session_id: str):
    """Proxy route to fetch and serve the published HTML from S3."""
    project = await get_project_by_session(session_id)
    if not project or not project.published_url:
        raise HTTPException(status_code=404, detail="Published app not found or not published yet.")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(project.published_url, timeout=15.0)
            resp.raise_for_status()
            return HTMLResponse(content=resp.text)
        except Exception as exc:
            logger.exception("Failed to fetch published app for session %s from %s", session_id, project.published_url)
            raise HTTPException(status_code=502, detail="Error fetching published app from S3.")
