"""Backend-enforced file safety contract for AI-generated app files."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TypedDict

from flow44.ai.generated_app_file_rules import PROTECTED_APP_FILE_RULES


class GeneratedAppContractError(ValueError):
    """Raised when generated output violates the app-generation contract."""


class GeneratedAppPathSafetyPromptContext(TypedDict):
    protected_files: list[str]
    protected_src_paths: list[str]
    protected_src_dirs: list[str]
    protected_name_patterns: list[str]


def generated_app_path_safety_prompt_context() -> GeneratedAppPathSafetyPromptContext:
    """Return protected path rules for prompt templates from the backend contract."""
    rules = PROTECTED_APP_FILE_RULES
    return {
        "protected_files": sorted(rules.files),
        "protected_src_paths": sorted(rules.src_paths),
        "protected_src_dirs": sorted(f"{'/'.join(path)}/*" for path in rules.src_dirs),
        "protected_name_patterns": [f"{prefix}*" for prefix in rules.name_prefixes]
        + [f"*{substring}*" for substring in rules.name_substrings],
    }


def normalize_generated_app_path(path: str) -> str:
    """Normalize a generated path and reject absolute or traversal paths."""
    if path.startswith(("/", "\\")):
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    normalized = path.replace("\\", "/").lstrip("/")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    return str(PurePosixPath(*parts))


def is_generated_app_path_allowed(path: str) -> bool:
    """Return whether AI generation may edit a path."""
    try:
        normalized = normalize_generated_app_path(path)
    except GeneratedAppContractError:
        return False

    return not _is_protected_generated_app_path(normalized)


def _is_protected_generated_app_path(normalized_path: str) -> bool:
    rules = PROTECTED_APP_FILE_RULES
    normalized = normalized_path.lower()
    parts = PurePosixPath(normalized).parts
    name = parts[-1]

    return (
        name in rules.files
        or normalized in rules.src_paths
        or name.startswith(rules.name_prefixes)
        or (len(parts) >= 2 and parts[:2] in rules.src_dirs)
        or any(substring in name for substring in rules.name_substrings)
    )


def validate_generated_app_edit_path(path: str) -> str:
    """Return a normalized path or raise for a protected target."""
    normalized = normalize_generated_app_path(path)
    if not is_generated_app_path_allowed(normalized):
        raise GeneratedAppContractError(f"AI generation may not edit protected file: {normalized}")
    return normalized
