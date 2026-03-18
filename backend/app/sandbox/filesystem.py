"""Sandboxed file-system operations.

Every path is resolved relative to the sandbox workspace directory.  A strict
prefix check prevents path-traversal attacks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langfuse.decorators import observe, langfuse_context

from app.config import settings
from app.sandbox.manager import sandbox_manager


@dataclass
class FileEntry:
    """A single node in a recursive file tree."""

    name: str
    path: str
    is_directory: bool
    children: list[FileEntry] | None = None


def _resolve_safe(session_id: str, relative_path: str) -> str:
    """Resolve *relative_path* inside the sandbox workspace and ensure
    it doesn't escape via ``..`` or symlinks.

    Raises ``PermissionError`` if the resolved path is outside the workspace.
    """
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise FileNotFoundError(f"No sandbox found for session {session_id}")

    workspace = os.path.realpath(sandbox.workspace_dir)
    # Strip leading slash so os.path.join behaves correctly
    cleaned = relative_path.lstrip("/")
    target = os.path.realpath(os.path.join(workspace, cleaned))

    if not target.startswith(workspace):
        raise PermissionError(f"Path traversal detected: {relative_path}")

    return target


async def read_file(session_id: str, path: str) -> str:
    """Return the text content of a file inside the sandbox."""
    full = _resolve_safe(session_id, path)
    with open(full, "r", encoding="utf-8") as fh:
        return fh.read()


@observe(name="write-file", as_type="span")
async def write_file(session_id: str, path: str, content: str) -> None:
    """Write *content* to a file inside the sandbox, creating parent dirs as needed."""
    full = _resolve_safe(session_id, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    # Add metadata about the file written
    langfuse_context.update_current_observation(
        metadata={"file_path": path, "content_length": len(content)}
    )


async def delete_file(session_id: str, path: str) -> None:
    """Delete a file (or empty directory) inside the sandbox."""
    full = _resolve_safe(session_id, path)
    if os.path.isdir(full):
        os.rmdir(full)
    else:
        os.remove(full)


async def list_files(session_id: str, path: str = "/") -> list[FileEntry]:
    """Return a recursive file tree rooted at *path* inside the sandbox."""
    full = _resolve_safe(session_id, path)
    if not os.path.isdir(full):
        raise NotADirectoryError(f"{path} is not a directory")

    sandbox = sandbox_manager.get_sandbox(session_id)
    assert sandbox is not None
    workspace = os.path.realpath(sandbox.workspace_dir)

    SKIP_DIRS = {"node_modules", ".git", ".next", "dist", ".cache", "__pycache__", ".vite"}

    def _build_tree(dir_path: str) -> list[FileEntry]:
        entries: list[FileEntry] = []
        try:
            items = sorted(os.listdir(dir_path))
        except PermissionError:
            return entries

        for name in items:
            if name.startswith(".") or name in SKIP_DIRS:
                continue
            abs_path = os.path.join(dir_path, name)
            # Monaco/TypeScript resolver עובדים עם URI בצורה עקבית (עם `/`).
            # ב-Windows `os.path.relpath` מחזיר `\`, וזה עלול לבלבל את רזולוציית ה-importים.
            rel_path = "/" + os.path.relpath(abs_path, workspace)
            rel_path = rel_path.replace("\\", "/")
            is_dir = os.path.isdir(abs_path)
            children = _build_tree(abs_path) if is_dir else None
            entries.append(FileEntry(name=name, path=rel_path, is_directory=is_dir, children=children))
        return entries

    return _build_tree(full)
