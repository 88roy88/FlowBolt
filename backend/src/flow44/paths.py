"""Shared preview/export URL path constants and helpers."""

from __future__ import annotations

import os
import re

PREVIEW_API_PREFIX = "/api/preview"
EXPORT_API_PREFIX = "/api/export"
PREVIEW_PROXY_SEGMENT = "proxy"
EXPORT_PUBLISHED_SEGMENT = "published"

# FastAPI route patterns (built from prefixes above)
PREVIEW_PROXY_ROUTE = f"/{{project_id}}/{PREVIEW_PROXY_SEGMENT}"
PREVIEW_PROXY_PATH_ROUTE = f"/{{project_id}}/{PREVIEW_PROXY_SEGMENT}/{{path:path}}"
EXPORT_PUBLISHED_ROUTE = f"/{EXPORT_PUBLISHED_SEGMENT}"
EXPORT_PUBLISHED_PATH_ROUTE = f"/{EXPORT_PUBLISHED_SEGMENT}/{{path:path}}"

_BASE_TAG_RE = re.compile(r'<base\s+href=["\'][^"\']*["\']\s*/?>', re.IGNORECASE)
_EXPORT_PUBLISHED_PREFIX = re.compile(
    rf"^{EXPORT_API_PREFIX.lstrip('/')}/[^/]+/{EXPORT_PUBLISHED_SEGMENT}/"
)


def preview_base_path(project_id: str) -> str:
    return f"{PREVIEW_API_PREFIX}/{project_id}/{PREVIEW_PROXY_SEGMENT}/"


def preview_proxy_path(project_id: str) -> str:
    return f"{PREVIEW_API_PREFIX}/{project_id}/{PREVIEW_PROXY_SEGMENT}"


def export_published_base_path(project_id: str) -> str:
    return f"{EXPORT_API_PREFIX}/{project_id}/{EXPORT_PUBLISHED_SEGMENT}/"


def export_published_app_path(project_id: str) -> str:
    return f"{EXPORT_API_PREFIX}/{project_id}/{EXPORT_PUBLISHED_SEGMENT}/"


def sandbox_path_env(project_id: str, *, api_base_url: str) -> dict[str, str]:
    """Env vars injected into sandbox workspaces (.env.local / .env.production.local)."""
    return {
        "VITE_PROJECT_ID": project_id,
        "VITE_PREVIEW_BASE": preview_base_path(project_id),
        "VITE_EXPORT_BASE": export_published_base_path(project_id),
        "VITE_API_BASE": api_base_url,
    }


def set_index_base_href(workspace_dir: str, base_path: str) -> None:
    """Set or replace the <base href> in workspace index.html."""
    index_path = os.path.join(workspace_dir, "index.html")
    with open(index_path, encoding="utf-8") as handle:
        html = handle.read()

    tag = f'<base href="{base_path}" />'
    if _BASE_TAG_RE.search(html):
        html = _BASE_TAG_RE.sub(tag, html, count=1)
    else:
        html = html.replace("<head>", f"<head>\n    {tag}", 1)

    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(html)


def strip_export_published_prefix(href: str) -> str:
    """Map a built asset URL back to a dist-relative path."""
    cleaned = href.lstrip("/\\")
    return _EXPORT_PUBLISHED_PREFIX.sub("", cleaned)
