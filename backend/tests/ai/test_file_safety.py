"""Tests for backend-enforced generated app file safety."""

from __future__ import annotations

import pytest

from flow44.ai.file_safety import (
    FileSafetyError,
    format_rejection_feedback,
    normalized_path_or_reject,
    protected_file_rules,
    screen_generated_files,
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


def test_screen_generated_files_rejects_protected_and_normalizes() -> None:
    files = [
        ("src/components/AssetMap.tsx", "a"),
        ("package.json", "b"),
        ("./src/App.tsx", "c"),
        ("../escape.ts", "d"),
    ]

    safe, rejections = screen_generated_files(files)

    assert safe == [
        ("src/components/AssetMap.tsx", "a"),
        ("src/App.tsx", "c"),
    ]
    assert len(rejections) == 2
    assert all(isinstance(r, FileSafetyError) for r in rejections)


def test_screen_generated_files_rejects_absolute_path() -> None:
    files = [("/etc/passwd", "content")]

    safe, rejections = screen_generated_files(files)

    assert safe == []
    assert len(rejections) == 1


def test_format_rejection_feedback_lists_each_rejection() -> None:
    feedback = format_rejection_feedback([FileSafetyError("first reason"), FileSafetyError("second reason")])

    assert "These files were rejected and not written:" in feedback
    assert "- first reason" in feedback
    assert "- second reason" in feedback
    assert "re-emit it in the same flowArtifact format" in feedback


def test_file_safety_prompt_context_uses_contract_values() -> None:
    context = protected_file_rules()

    assert "src/main.tsx" in context["protected_paths"]
    assert "**/package.json" in context["protected_patterns"]
    assert "src/platform/**" in context["protected_patterns"]
    assert "**/vite.config.*" in context["protected_patterns"]
