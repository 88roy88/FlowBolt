"""Backend-enforced safety and dependency contract for AI-generated app files."""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath, PureWindowsPath

from flow44.ai.generated_app_file_rules import (
    PROTECTED_APP_FILE_RULES,
    GeneratedAppPathSafetyPromptContext,
)


class GeneratedAppContractError(ValueError):
    """Raised when generated output violates the app-generation contract."""


_IMPORT_PATTERNS = (
    re.compile(r"""(?:import|export)\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']"""),
    re.compile(r"""import\s*\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""require\s*\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""@import\s+(?:url\()?["']([^"']+)["']"""),
)


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


def extract_external_imports(content: str) -> set[str]:
    """Extract external module specifiers from TypeScript/JavaScript source."""
    imports: set[str] = set()
    for pattern in _IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            specifier = match.group(1)
            if not specifier.startswith((".", "/")):
                imports.add(specifier)
    return imports


def find_disallowed_external_imports(content: str, allowed_imports: list[str]) -> set[str]:
    """Return external imports not covered by the explicit dependency contract."""
    allowed = {"react", "react-dom", *allowed_imports}
    return {
        specifier
        for specifier in extract_external_imports(content)
        if not any(specifier == package or specifier.startswith(f"{package}/") for package in allowed)
    }


def validate_generated_app_file_contract(path: str, content: str, allowed_imports: list[str]) -> str:
    """Validate a generated file target and its external imports."""
    normalized = validate_generated_app_path_allowed(path)
    disallowed = sorted(find_disallowed_external_imports(content, allowed_imports))
    if disallowed:
        raise GeneratedAppContractError(
            f"Generated file {normalized} imports unselected packages: {', '.join(disallowed)}"
        )
    return normalized


logger = logging.getLogger(__name__)


def filter_safe_generated_files(
    generated: list[tuple[str, str]],
    *,
    source: str,
    allowed_imports: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Return generated files with protected/unsafe/disallowed-import paths dropped and kept paths normalized."""
    safe: list[tuple[str, str]] = []
    for path, content in generated:
        try:
            if allowed_imports is None:
                normalized = validate_generated_app_path_allowed(path)
            else:
                normalized = validate_generated_app_file_contract(path, content, allowed_imports)
            safe.append((normalized, content))
        except GeneratedAppContractError as exc:
            logger.warning("Dropping generated file (%s): %s (%s)", source, path, exc)
    return safe
