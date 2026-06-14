"""Tests for backend-enforced generated app file and import safety."""

from __future__ import annotations

import pytest

from flow44.ai.generated_app_contract import (
    GeneratedAppContractError,
    assert_generated_code_contract,
    disallowed_external_imports,
    is_generated_app_file_allowed,
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
        "backend/server.py",
    ],
)
def test_protected_generated_app_files_are_rejected(path: str) -> None:
    assert not is_generated_app_file_allowed(path)


def test_normal_app_source_file_is_allowed() -> None:
    assert is_generated_app_file_allowed("src/components/AssetMap.tsx")


def test_unselected_external_import_is_rejected() -> None:
    content = "import { Button } from '@mui/material';"

    with pytest.raises(GeneratedAppContractError, match="@mui/material"):
        assert_generated_code_contract("src/App.tsx", content, [])


def test_selected_import_and_react_subpath_are_allowed() -> None:
    content = """
import React from 'react';
import { createRoot } from 'react-dom/client';
import { Button } from '@mui/material';
import { helper } from './helper';
"""

    assert disallowed_external_imports(content, ["@mui/material"]) == set()
    assert assert_generated_code_contract("src/App.tsx", content, ["@mui/material"]) == "src/App.tsx"


def test_dynamic_unselected_import_is_rejected() -> None:
    assert disallowed_external_imports("const dialog = import('@mui/material/Dialog');", []) == {
        "@mui/material/Dialog"
    }


def test_css_package_import_is_rejected() -> None:
    assert disallowed_external_imports("@import 'unselected-theme/styles.css';", []) == {
        "unselected-theme/styles.css"
    }
