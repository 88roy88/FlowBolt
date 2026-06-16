"""Tests for backend-enforced generated app file and import safety."""

from __future__ import annotations

import pytest

from flow44.ai.generated_app_contract import (
    GeneratedAppContractError,
    find_disallowed_external_imports,
    generated_app_path_safety_prompt_context,
    is_generated_app_path_allowed,
    validate_generated_app_path_allowed,
    validate_generated_app_file_contract,
)


@pytest.mark.parametrize(
    "path",
    [
        "package.json",
        "pnpm-lock.yaml",
        "src/features/package.json",
        "vite.config.ts",
        "index.html",
        ".env.local",
        "src/main.tsx",
        "src/vite-env.d.ts",
        "src/platform/internal/README.md",
    ],
)
def test_protected_generated_app_files_are_rejected(path: str) -> None:
    assert not is_generated_app_path_allowed(path)


def test_normal_app_source_file_is_allowed() -> None:
    assert is_generated_app_path_allowed("src/components/AssetMap.tsx")


def test_unselected_external_import_is_rejected() -> None:
    content = "import { Button } from '@mui/material';"

    with pytest.raises(GeneratedAppContractError, match="@mui/material"):
        validate_generated_app_file_contract("src/App.tsx", content, [])


@pytest.mark.parametrize(
    "path",
    [
        "/src/App.tsx",
        "\\src\\App.tsx",
        "C:\\src\\App.tsx",
        "C:src\\App.tsx",
        "\\\\server\\share\\src\\App.tsx",
        "../src/App.tsx",
        "src/../App.tsx",
    ],
)
def test_unsafe_generated_paths_are_rejected(path: str) -> None:
    with pytest.raises(GeneratedAppContractError):
        validate_generated_app_path_allowed(path)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("./src/components/AssetMap.tsx", "src/components/AssetMap.tsx"),
        ("src/components/AssetMap.tsx", "src/components/AssetMap.tsx"),
        ("src/./components/AssetMap.tsx", "src/components/AssetMap.tsx"),
        ("src\\components\\AssetMap.tsx", "src/components/AssetMap.tsx"),
    ],
)
def test_generated_path_is_normalized_for_posix_and_windows_paths(path: str, expected: str) -> None:
    assert validate_generated_app_path_allowed(path) == expected


def test_file_safety_prompt_context_uses_contract_values() -> None:
    context = generated_app_path_safety_prompt_context()

    assert "package.json" in context["protected_files"]
    assert "src/main.tsx" in context["protected_src_paths"]
    assert "src/platform/*" in context["protected_src_dirs"]
    assert "vite.config.*" in context["protected_name_patterns"]


def test_selected_import_and_react_subpath_are_allowed() -> None:
    content = """
import React from 'react';
import { createRoot } from 'react-dom/client';
import { Button } from '@mui/material';
import { helper } from './helper';
"""

    assert find_disallowed_external_imports(content, ["@mui/material"]) == set()
    assert validate_generated_app_file_contract("src/App.tsx", content, ["@mui/material"]) == "src/App.tsx"


def test_dynamic_unselected_import_is_rejected() -> None:
    assert find_disallowed_external_imports("const dialog = import('@mui/material/Dialog');", []) == {
        "@mui/material/Dialog"
    }


def test_css_package_import_is_rejected() -> None:
    assert find_disallowed_external_imports("@import 'unselected-theme/styles.css';", []) == {
        "unselected-theme/styles.css"
    }
