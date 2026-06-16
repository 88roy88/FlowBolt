"""Backend-enforced safety and dependency contract for AI-generated app files."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TypedDict

from flow44.ai.generated_app_file_rules import (
    PROTECTED_FILES,
    PROTECTED_NAME_PREFIXES,
    PROTECTED_NAME_SUBSTRINGS,
    PROTECTED_ROOT_DIRS,
    PROTECTED_SRC_DIRS,
    PROTECTED_SRC_PATHS,
)


class GeneratedAppContractError(ValueError):
    """Raised when generated output violates the app-generation contract."""


class GeneratedAppPathSafetyPromptContext(TypedDict):
    protected_files: list[str]
    protected_src_paths: list[str]
    protected_src_dirs: list[str]
    protected_root_dirs: list[str]
    protected_name_patterns: list[str]


_IMPORT_PATTERNS = (
    re.compile(r"""(?:import|export)\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']"""),
    re.compile(r"""import\s*\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""require\s*\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""@import\s+(?:url\()?["']([^"']+)["']"""),
)


def generated_app_path_safety_prompt_context() -> GeneratedAppPathSafetyPromptContext:
    """Return protected path rules for prompt templates from the backend contract."""
    return {
        "protected_files": sorted(PROTECTED_FILES),
        "protected_src_paths": sorted(PROTECTED_SRC_PATHS),
        "protected_src_dirs": sorted(f"{'/'.join(path)}/*" for path in PROTECTED_SRC_DIRS),
        "protected_root_dirs": sorted(f"{path}/*" for path in PROTECTED_ROOT_DIRS),
        "protected_name_patterns": [f"{prefix}*" for prefix in PROTECTED_NAME_PREFIXES]
        + [f"*{substring}*" for substring in PROTECTED_NAME_SUBSTRINGS],
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

    parts = tuple(part.lower() for part in PurePosixPath(normalized).parts)
    name = parts[-1].lower()
    return not (
        name in PROTECTED_FILES
        or normalized.lower() in PROTECTED_SRC_PATHS
        or name.startswith(PROTECTED_NAME_PREFIXES)
        or parts[0] in PROTECTED_ROOT_DIRS
        or (len(parts) >= 2 and parts[:2] in PROTECTED_SRC_DIRS)
        or any(substring in name for substring in PROTECTED_NAME_SUBSTRINGS)
    )


def validate_generated_app_edit_path(path: str) -> str:
    """Return a normalized path or raise for a protected target."""
    normalized = normalize_generated_app_path(path)
    if not is_generated_app_path_allowed(normalized):
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


def assert_generated_app_code_allowed(path: str, content: str, allowed_imports: list[str]) -> str:
    """Validate a generated file target and its external imports."""
    normalized = validate_generated_app_edit_path(path)
    disallowed = sorted(find_disallowed_external_imports(content, allowed_imports))
    if disallowed:
        raise GeneratedAppContractError(
            f"Generated file {normalized} imports unselected packages: {', '.join(disallowed)}"
        )
    return normalized
