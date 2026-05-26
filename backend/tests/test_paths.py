"""Tests for shared preview/export path helpers."""

from flow44.paths import (
    EXPORT_PUBLISHED_PATH_ROUTE,
    EXPORT_PUBLISHED_ROUTE,
    PREVIEW_PROXY_PATH_ROUTE,
    PREVIEW_PROXY_ROUTE,
    export_published_app_path,
    export_published_base_path,
    preview_base_path,
    preview_proxy_path,
    sandbox_path_env,
    set_index_base_href,
    strip_export_published_prefix,
)


def test_api_route_patterns() -> None:
    assert PREVIEW_PROXY_ROUTE == "/{project_id}/proxy"
    assert PREVIEW_PROXY_PATH_ROUTE == "/{project_id}/proxy/{path:path}"
    assert EXPORT_PUBLISHED_ROUTE == "/published"
    assert EXPORT_PUBLISHED_PATH_ROUTE == "/published/{path:path}"


def test_preview_paths() -> None:
    project_id = "abc-123"
    assert preview_base_path(project_id) == "/api/preview/abc-123/proxy/"
    assert preview_proxy_path(project_id) == "/api/preview/abc-123/proxy"


def test_export_paths() -> None:
    project_id = "abc-123"
    assert export_published_base_path(project_id) == "/api/export/abc-123/published/"
    assert export_published_app_path(project_id) == "/api/export/abc-123/published/"


def test_sandbox_path_env() -> None:
    env = sandbox_path_env("abc-123", api_base_url="http://localhost:8000")
    assert env["VITE_PROJECT_ID"] == "abc-123"
    assert env["VITE_PREVIEW_BASE"] == "/api/preview/abc-123/proxy/"
    assert env["VITE_EXPORT_BASE"] == "/api/export/abc-123/published/"
    assert env["VITE_API_BASE"] == "http://localhost:8000"


def test_set_index_base_href(tmp_path) -> None:  # type: ignore[type-arg]
    index_path = tmp_path / "index.html"
    index_path.write_text("<html><head><title>App</title></head><body></body></html>", encoding="utf-8")

    set_index_base_href(str(tmp_path), "/api/export/id/published/")
    content = index_path.read_text(encoding="utf-8")
    assert '<base href="/api/export/id/published/" />' in content

    set_index_base_href(str(tmp_path), "/api/preview/id/proxy/")
    content = index_path.read_text(encoding="utf-8")
    assert '<base href="/api/preview/id/proxy/" />' in content
    assert "export/id/published" not in content


def test_strip_export_published_prefix() -> None:
    href = "/api/export/proj-123/published/assets/index.js"
    assert strip_export_published_prefix(href) == "assets/index.js"
