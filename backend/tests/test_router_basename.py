"""Tests for routerBasename template utility."""

from __future__ import annotations

from pathlib import Path

from flow44.config import settings


def test_router_basename_reads_base_tag() -> None:
    path = Path(settings.TEMPLATE_DIR) / "src" / "utils" / "routerBasename.ts"
    content = path.read_text(encoding="utf-8")
    assert "getRouterBasename" in content
    assert "querySelector('base')" in content
    assert "replace(/\\/$/, '')" in content
