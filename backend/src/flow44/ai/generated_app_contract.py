"""Backend-enforced file safety contract for AI-generated app files."""

from __future__ import annotations

from pathlib import PurePosixPath

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


def generated_app_path_safety_prompt_context() -> dict[str, list[str]]:
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
