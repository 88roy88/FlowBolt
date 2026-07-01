"""Tests for backend-enforced generated app file safety."""

from __future__ import annotations

import pytest

from flow44.ai.file_safety import (
    FileSafetyError,
    drop_protected_files,
    normalized_path_or_reject,
    protected_file_rules,
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
    with pytest.raises(FileSafetyError):
        normalized_path_or_reject(path)


def test_normal_app_source_file_is_allowed() -> None:
    assert normalized_path_or_reject("src/components/AssetMap.tsx") == "src/components/AssetMap.tsx"


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
    with pytest.raises(FileSafetyError):
        normalized_path_or_reject(path)


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
    assert normalized_path_or_reject(path) == expected


def test_drop_protected_files_drops_protected_and_normalizes() -> None:
    files = [
        ("src/components/AssetMap.tsx", "a"),
        ("package.json", "b"),        # protected -> dropped
        ("./src/App.tsx", "c"),        # kept, normalized to src/App.tsx
        ("../escape.ts", "d"),         # unsafe -> dropped
    ]
    assert drop_protected_files(files, source="test") == [
        ("src/components/AssetMap.tsx", "a"),
        ("src/App.tsx", "c"),
    ]


def test_file_safety_prompt_context_uses_contract_values() -> None:
    context = protected_file_rules()

    assert "package.json" in context["protected_paths"]
    assert "src/main.tsx" in context["protected_paths"]
    assert "src/platform/*" in context["protected_patterns"]
    assert "vite.config.*" in context["protected_patterns"]
