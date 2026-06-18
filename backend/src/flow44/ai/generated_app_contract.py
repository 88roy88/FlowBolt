"""Backend-enforced file safety contract for AI-generated app files."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from flow44.ai.generated_app_file_rules import (
    PROTECTED_APP_FILE_RULES,
    GeneratedAppPathSafetyPromptContext,
)


class GeneratedAppContractError(ValueError):
    """Raised when generated output violates the app-generation contract."""


def generated_app_path_safety_prompt_context() -> GeneratedAppPathSafetyPromptContext:
    """Return protected path rules for prompt templates from the backend contract."""
    return PROTECTED_APP_FILE_RULES.prompt_context()


def validate_and_normalize_generated_app_path(path: str) -> str:
    """Validate a generated path is relative and return its canonical POSIX form."""
    return str(PurePosixPath(*_safe_generated_app_path_parts(path)))


def _safe_generated_app_path_parts(path: str) -> tuple[str, ...]:
    """Return safe relative path parts or raise for absolute/traversal input."""
    parsed = PureWindowsPath(path)
    if parsed.drive or parsed.root:
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    parts = parsed.parts
    if not parts or any(part == ".." for part in parts):
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    return parts


def is_generated_app_path_allowed(path: str) -> bool:
    """Return whether AI generation may edit a path."""
    try:
        normalized = validate_and_normalize_generated_app_path(path)
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


def validate_generated_app_path_allowed(path: str) -> str:
    """Return a normalized path or raise for a protected target."""
    normalized = validate_and_normalize_generated_app_path(path)
    if _is_protected_generated_app_path(normalized):
        raise GeneratedAppContractError(f"AI generation may not edit protected file: {normalized}")
    return normalized
