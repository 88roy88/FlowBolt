"""Shared preview/export URL path constants and helpers."""

from __future__ import annotations

import re
from typing import Literal

PREVIEW_API_PREFIX = "/api/preview"
EXPORT_API_PREFIX = "/api/export"
PREVIEW_PROXY_SEGMENT = "proxy"
EXPORT_PUBLISHED_SEGMENT = "published"

PREVIEW_PROXY_ROUTE = f"/{{project_id}}/{PREVIEW_PROXY_SEGMENT}"
PREVIEW_PROXY_PATH_ROUTE = f"/{{project_id}}/{PREVIEW_PROXY_SEGMENT}/{{path:path}}"
EXPORT_PUBLISHED_ROUTE = f"/{EXPORT_PUBLISHED_SEGMENT}"
EXPORT_PUBLISHED_PATH_ROUTE = f"/{EXPORT_PUBLISHED_SEGMENT}/{{path:path}}"

_EXPORT_PUBLISHED_PREFIX = re.compile(
    rf"^{EXPORT_API_PREFIX.lstrip('/')}/[^/]+/{EXPORT_PUBLISHED_SEGMENT}/"
)

SandboxBaseMode = Literal["preview", "publish"]


def preview_base_path(project_id: str) -> str:
    return f"{PREVIEW_API_PREFIX}/{project_id}/{PREVIEW_PROXY_SEGMENT}/"


def preview_proxy_path(project_id: str) -> str:
    return f"{PREVIEW_API_PREFIX}/{project_id}/{PREVIEW_PROXY_SEGMENT}"


def export_published_base_path(project_id: str) -> str:
    return f"{EXPORT_API_PREFIX}/{project_id}/{EXPORT_PUBLISHED_SEGMENT}/"


def sandbox_public_base_env(project_id: str, mode: SandboxBaseMode) -> dict[str, str]:
    """Vite/React Router public base path for preview or publish builds."""
    if mode == "publish":
        return {"VITE_BASE_PATH": export_published_base_path(project_id)}
    return {"VITE_BASE_PATH": preview_base_path(project_id)}


def sandbox_path_env(project_id: str, *, api_base_url: str) -> dict[str, str]:
    """Env vars for sandbox preview (.env.local and dev server)."""
    return {
        **sandbox_public_base_env(project_id, "preview"),
        "VITE_API_BASE": api_base_url,
    }


def strip_export_published_prefix(href: str) -> str:
    """Map a built asset URL back to a dist-relative path."""
    cleaned = href.lstrip("/\\")
    return _EXPORT_PUBLISHED_PREFIX.sub("", cleaned)
