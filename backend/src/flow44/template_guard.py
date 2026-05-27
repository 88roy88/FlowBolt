"""Load protected template file paths from the pnpm project template manifest."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

MANIFEST_FILENAME = ".template-guard.json"


def normalize_workspace_relative_path(path: str) -> str:
    """Normalize a workspace-relative path to forward slashes and validate it is safe."""
    normalized = path.replace("\\", "/").strip()
    if not normalized:
        msg = f"Invalid {MANIFEST_FILENAME}: empty path in protected_files"
        raise ValueError(msg)

    if normalized.startswith("./"):
        normalized = normalized.removeprefix("./")

    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        msg = f"Invalid {MANIFEST_FILENAME}: absolute path not allowed: {path!r}"
        raise ValueError(msg)
    if ".." in pure.parts:
        msg = f"Invalid {MANIFEST_FILENAME}: path traversal not allowed: {path!r}"
        raise ValueError(msg)

    return pure.as_posix()


def load_protected_file_paths(template_dir: str) -> tuple[str, ...]:
    """Return workspace-relative paths that must not be overwritten by AI codegen/fix.

    If the manifest is missing, returns an empty tuple (no protected files).
    """
    manifest_path = Path(template_dir) / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return ()

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = data.get("protected_files")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        msg = f"Invalid {MANIFEST_FILENAME}: protected_files must be a list of strings"
        raise ValueError(msg)

    return tuple(normalize_workspace_relative_path(item) for item in paths)


def is_protected_workspace_path(path: str, protected: frozenset[str]) -> bool:
    """Return True when an AI file action targets a protected workspace-relative path."""
    if not protected:
        return False
    try:
        return normalize_workspace_relative_path(path) in protected
    except ValueError:
        return False
