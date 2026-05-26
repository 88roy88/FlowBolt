"""Tests for shared preview/export path helpers."""

import flow44.paths as paths_module

from flow44.paths import (
    EXPORT_PUBLISHED_PATH_ROUTE,
    EXPORT_PUBLISHED_ROUTE,
    PREVIEW_PROXY_PATH_ROUTE,
    PREVIEW_PROXY_ROUTE,
    export_published_base_path,
    preview_base_path,
    preview_proxy_path,
    sandbox_path_env,
    sandbox_public_base_env,
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


def test_sandbox_public_base_env() -> None:
    project_id = "abc-123"
    preview = sandbox_public_base_env(project_id, "preview")
    publish = sandbox_public_base_env(project_id, "publish")
    assert preview["VITE_PUBLIC_BASE_PATH"] == "/api/preview/abc-123/proxy/"
    assert publish["VITE_PUBLIC_BASE_PATH"] == "/api/export/abc-123/published/"


def test_sandbox_path_env() -> None:
    env = sandbox_path_env("abc-123", api_base_url="http://localhost:8000")
    assert env["VITE_PUBLIC_BASE_PATH"] == "/api/preview/abc-123/proxy/"
    assert env["VITE_API_BASE"] == "http://localhost:8000"


def test_strip_export_published_prefix() -> None:
    href = "/api/export/proj-123/published/assets/index.js"
    assert strip_export_published_prefix(href) == "assets/index.js"


def test_set_index_base_href_removed() -> None:
    assert not hasattr(paths_module, "set_index_base_href")
