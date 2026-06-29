"""Backend-enforced file safety contract for AI-generated app files."""

from __future__ import annotations

import logging
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
    parts = parsed.parts
    if parsed.drive or parsed.root or not parts or ".." in parts:
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    return parts


def validate_generated_app_path_allowed(path: str) -> str:
    """Return a normalized path or raise for a protected target."""
    normalized = validate_and_normalize_generated_app_path(path)
    if PROTECTED_APP_FILE_RULES.is_protected(normalized):
        raise GeneratedAppContractError(f"AI generation may not edit protected file: {normalized}")
    return normalized


logger = logging.getLogger(__name__)


def filter_safe_generated_files(generated: list[tuple[str, str]], *, source: str) -> list[tuple[str, str]]:
    """Return generated files with protected/unsafe paths dropped and kept paths normalized."""
    safe: list[tuple[str, str]] = []
    for path, content in generated:
        try:
            safe.append((validate_generated_app_path_allowed(path), content))
        except GeneratedAppContractError:
            logger.warning("Dropping protected generated file (%s): %s", source, path)
    return safe
