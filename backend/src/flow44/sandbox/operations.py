# Review TODO: rename this file. import it in the pnpm mixin and expose from there.
from __future__ import annotations

import base64
import logging
import os
import re

from langfuse.decorators import observe

from flow44.config import settings
from flow44.paths import (
    export_published_base_path,
    preview_base_path,
    sandbox_path_env,
    set_index_base_href,
    strip_export_published_prefix,
)
from flow44.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)


class BuildError(Exception):
    """Raised when the build process fails."""


def _inline_css_assets(html: str, dist_dir: str) -> str:
    """Inline CSS stylesheets from the dist directory into the HTML."""

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
    return re.sub(
        r'<link\s[^>]*?rel=["\']stylesheet["\'][^>]*?href=["\']([^"\']+)["\'][^>]*/?>',
        inline_css,
        html,
        flags=re.IGNORECASE,
    )


def _inline_js_assets(html: str, dist_dir: str) -> str:
    """Inline JS scripts from the dist directory into the HTML."""

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

    return re.sub(
        r'<script\s[^>]*?src=["\']([^"\']+)["\'][^>]*?>\s*</script>',
        inline_js,
        html,
        flags=re.IGNORECASE,
    )


def _resolve_asset_path(dist_dir: str, href: str) -> str | None:
    cleaned = strip_export_published_prefix(href.lstrip("/\\"))
    candidate = os.path.join(dist_dir, cleaned)
    try:
        if os.path.commonpath([os.path.realpath(dist_dir), os.path.realpath(candidate)]) != os.path.realpath(dist_dir):
            return None
    except ValueError:
        return None
    return candidate


def _inline_favicon(html: str, dist_dir: str, workspace_dir: str) -> str:
    """Replace favicon <link> with an inline data URI."""

    def replace_favicon(match: re.Match[str]) -> str:
        href = match.group(1)
        # Try dist first, then workspace root (dev favicons live in public/)
        for base in (dist_dir, os.path.join(workspace_dir, "public"), workspace_dir):
            path = os.path.join(base, href.lstrip("/\\"))
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


async def build_dist(project_id: str) -> str:
    """Build the project and return the dist directory path."""
    sandbox = sandbox_manager.get_sandbox(project_id)
    if sandbox is None:
        raise ValueError(f"No sandbox found for project {project_id}")

    workspace_dir = sandbox.workspace_dir
    env_file = os.path.join(workspace_dir, ".env.production.local")
    set_index_base_href(workspace_dir, export_published_base_path(project_id))
    if hasattr(sandbox, "refresh_vite_config_stamps"):
        sandbox.refresh_vite_config_stamps()
    try:
        env_vars = sandbox_path_env(project_id, api_base_url=settings.EXPORT_API_BASE_URL)
        env_lines = [f"{key}={value}" for key, value in env_vars.items()]
        with open(env_file, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            f.write("\n".join(env_lines) + "\n")

        build_output_lines: list[str] = []
        async for line in sandbox.exec("pnpm build"):
            build_output_lines.append(line)
        build_output = "".join(build_output_lines)
    finally:
        set_index_base_href(workspace_dir, preview_base_path(project_id))
        try:
            os.remove(env_file)
        except OSError:
            pass

    dist_dir = os.path.join(workspace_dir, "dist")
    index_path = os.path.join(dist_dir, "index.html")
    if not os.path.isfile(index_path):  # noqa: ASYNC240
        raise BuildError(f"Build failed or dist/index.html not found.\n\n{build_output}")

    return dist_dir


@observe(name="build-single-html")  # type: ignore[untyped-decorator]
async def build_single_html(project_id: str) -> str:
    """Build the project and return a single self-contained HTML string."""
    dist_dir = await build_dist(project_id)
    sandbox = sandbox_manager.get_sandbox(project_id)
    if sandbox is None:
        raise ValueError(f"No sandbox found for project {project_id}")

    workspace_dir = sandbox.workspace_dir
    index_path = os.path.join(dist_dir, "index.html")

    with open(index_path, encoding="utf-8", errors="replace") as f:  # noqa: ASYNC230
        html = f.read()

    # --- Inline CSS ---
    html = _inline_css_assets(html, dist_dir)

    # --- Inline JS ---
    html = _inline_js_assets(html, dist_dir)

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
