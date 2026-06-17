"""Tests for backend-enforced generated app file safety."""

from __future__ import annotations

import pytest

from flow44.ai.generated_app_contract import (
    GeneratedAppContractError,
    generated_app_path_safety_prompt_context,
    is_generated_app_path_allowed,
    validate_generated_app_path_allowed,
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


@pytest.mark.parametrize("path", ["/src/App.tsx", "../src/App.tsx", "src/../App.tsx"])
def test_unsafe_generated_paths_are_rejected(path: str) -> None:
    with pytest.raises(GeneratedAppContractError):
        validate_generated_app_path_allowed(path)


def test_generated_path_is_normalized() -> None:
    assert validate_generated_app_path_allowed("src\\components\\AssetMap.tsx") == "src/components/AssetMap.tsx"


def test_file_safety_prompt_context_uses_contract_values() -> None:
    context = generated_app_path_safety_prompt_context()

    assert "package.json" in context["protected_files"]
    assert "src/main.tsx" in context["protected_src_paths"]
    assert "src/platform/*" in context["protected_src_dirs"]
    assert "vite.config.*" in context["protected_name_patterns"]
