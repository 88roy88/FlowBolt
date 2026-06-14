"""Public base paths used by generated apps."""

from __future__ import annotations

import re

PREVIEW_API_PREFIX = "/api/preview"
SHARED_PREFIX = "/shared"

_PUBLIC_BASE_PREFIX = re.compile(r"^(?:api/preview/[^/]+/proxy|shared/[^/]+)/")


def preview_base_path(project_id: str) -> str:
    return f"{PREVIEW_API_PREFIX}/{project_id}/proxy/"


def shared_base_path(handle: str) -> str:
    return f"{SHARED_PREFIX}/{handle}/"


def sandbox_path_env(*, public_base: str, api_base_url: str) -> dict[str, str]:
    """Vite env vars for preview/export/publish builds."""
    return {
        # VITE_BASE keeps existing workspaces compatible; VITE_BASE_PATH is the
        # clearer name used by the current template.
        "VITE_BASE": public_base,
        "VITE_BASE_PATH": public_base,
        "VITE_API_BASE": api_base_url,
    }


def strip_public_base_prefix(href: str) -> str:
    """Map a generated public asset URL back to a dist-relative path."""
    return _PUBLIC_BASE_PREFIX.sub("", href.lstrip("/\\"))
