"""Tests for platform routerBasename helper in the project template."""

from __future__ import annotations

from pathlib import Path

from flow44.config import settings


def test_router_basename_uses_base_url() -> None:
    path = Path(settings.TEMPLATE_DIR) / "src" / "platform" / "routerBasename.ts"
    content = path.read_text(encoding="utf-8")
    assert "getRouterBasename" in content
    assert "import.meta.env.BASE_URL" in content
    assert "VITE_BASE_PATH" not in content
    assert "querySelector('base')" not in content
    assert "replace(/" in content and "/+$/" in content
