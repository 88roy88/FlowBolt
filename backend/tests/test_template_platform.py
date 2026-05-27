"""Tests for template platform routing ownership and contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from flow44.config import settings


@pytest.fixture
def template_root() -> Path:
    return Path(settings.TEMPLATE_DIR)


def test_template_guard_manifest_exists(template_root: Path) -> None:
    manifest = template_root / ".template-guard.json"
    assert manifest.is_file()
    import json

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["protected_files"] == ["src/platform/routerBasename.ts"]


def test_routing_md_exists(template_root: Path) -> None:
    routing_md = template_root / "ROUTING.md"
    assert routing_md.is_file()
    content = routing_md.read_text(encoding="utf-8")
    assert "VITE_BASE_PATH" in content
    assert "import.meta.env.BASE_URL" in content
    assert "getRouterBasename" in content
    assert "src/platform/routerBasename.ts" in content
    assert "Link" in content
    assert "Never remove" in content or "never remove" in content.lower()
    assert "vite.config.ts" in content
    assert "Never use `<a href=\"/…\">`" in content or "never `<a href=\"/…\">`" in content.lower()
    assert "/api/preview" not in content or "Do not hardcode" in content


def test_vite_config_does_not_override_base_url_define(template_root: Path) -> None:
    content = (template_root / "vite.config.ts").read_text(encoding="utf-8")
    assert "import.meta.env.BASE_URL" not in content
    assert "env.BASE_URL" not in content


def test_no_flowbolt_stub(template_root: Path) -> None:
    assert not (template_root / "flowbolt-stub").exists()
    assert not (template_root / "platform-stub").exists()


def test_no_flowbolt_paths_in_template(template_root: Path) -> None:
    skip_dirs = {"node_modules", "dist", ".git"}
    for path in template_root.rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".ts", ".tsx", ".md", ".json"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "flowbolt" not in text.lower(), f"flowbolt reference in {path.relative_to(template_root)}"


def test_vite_config_uses_public_base_path(template_root: Path) -> None:
    content = (template_root / "vite.config.ts").read_text(encoding="utf-8")
    assert "VITE_BASE_PATH" in content
    assert "const base = env.VITE_BASE_PATH" in content or "env.VITE_BASE_PATH" in content
    assert "base," in content or "base:" in content


def test_index_html_has_no_base_tag(template_root: Path) -> None:
    content = (template_root / "index.html").read_text(encoding="utf-8")
    assert "<base" not in content.lower()


def test_platform_router_basename_always_present(template_root: Path) -> None:
    path = template_root / "src" / "platform" / "routerBasename.ts"
    assert path.is_file()


def test_no_platform_app_router_in_template(template_root: Path) -> None:
    assert not (template_root / "src" / "platform" / "AppRouter.tsx").exists()


def test_main_tsx_renders_app_directly(template_root: Path) -> None:
    content = (template_root / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "<App />" in content or "<App/>" in content
    assert "BrowserRouter" not in content
    assert "react-router-dom" not in content


def test_package_json_no_react_router_by_default(template_root: Path) -> None:
    import json

    pkg = json.loads((template_root / "package.json").read_text(encoding="utf-8"))
    assert "react-router-dom" not in pkg.get("dependencies", {})
