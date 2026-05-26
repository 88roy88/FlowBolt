"""Tests for template platform file guard manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.template_guard import (
    MANIFEST_FILENAME,
    is_protected_workspace_path,
    load_protected_file_paths,
    normalize_workspace_relative_path,
)


def test_load_protected_file_paths_from_template() -> None:
    paths = load_protected_file_paths(settings.TEMPLATE_DIR)
    assert paths == ("src/platform/routerBasename.ts",)


def test_manifest_exists_in_template() -> None:
    manifest = Path(settings.TEMPLATE_DIR) / MANIFEST_FILENAME
    assert manifest.is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["protected_files"] == ["src/platform/routerBasename.ts"]


def test_load_returns_empty_when_manifest_missing(tmp_path: Path) -> None:
    assert load_protected_file_paths(str(tmp_path)) == ()


def test_load_raises_on_invalid_manifest_shape(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(json.dumps({"protected_files": "not-a-list"}), encoding="utf-8")
    with pytest.raises(ValueError, match="protected_files"):
        load_protected_file_paths(str(tmp_path))


def test_rejects_absolute_path(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(
        json.dumps({"protected_files": ["/etc/passwd"]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="absolute path"):
        load_protected_file_paths(str(tmp_path))


def test_rejects_path_traversal(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(
        json.dumps({"protected_files": ["src/../secret.ts"]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="path traversal"):
        load_protected_file_paths(str(tmp_path))


def test_rejects_empty_path(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(json.dumps({"protected_files": ["  "]}), encoding="utf-8")
    with pytest.raises(ValueError, match="empty path"):
        load_protected_file_paths(str(tmp_path))


def test_normalizes_backslashes(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(
        json.dumps({"protected_files": ["src\\platform\\routerBasename.ts"]}),
        encoding="utf-8",
    )
    assert load_protected_file_paths(str(tmp_path)) == ("src/platform/routerBasename.ts",)


def test_strips_leading_dot_slash(tmp_path: Path) -> None:
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.write_text(
        json.dumps({"protected_files": ["./src/platform/routerBasename.ts"]}),
        encoding="utf-8",
    )
    assert load_protected_file_paths(str(tmp_path)) == ("src/platform/routerBasename.ts",)


def test_normalize_workspace_relative_path() -> None:
    assert normalize_workspace_relative_path("src\\platform\\x.ts") == "src/platform/x.ts"


def test_is_protected_workspace_path_matches_normalized_variants() -> None:
    protected = frozenset({"src/platform/routerBasename.ts"})
    assert is_protected_workspace_path("src/platform/routerBasename.ts", protected)
    assert is_protected_workspace_path("src\\platform\\routerBasename.ts", protected)
    assert is_protected_workspace_path("./src/platform/routerBasename.ts", protected)
    assert not is_protected_workspace_path("src/App.tsx", protected)
    assert not is_protected_workspace_path("../src/platform/routerBasename.ts", protected)
    assert not is_protected_workspace_path("/src/platform/routerBasename.ts", protected)
