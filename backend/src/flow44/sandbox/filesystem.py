from __future__ import annotations

import os
from dataclasses import dataclass

from langfuse.decorators import observe, langfuse_context

from flow44.sandbox.manager import sandbox_manager


@dataclass
class FileEntry:
    name: str
    path: str
    is_directory: bool
    children: list[FileEntry] | None = None


def _resolve_safe(session_id: str, relative_path: str) -> tuple[str, str]:
    """Returns (resolved_path, workspace_root). Raises FileNotFoundError / PermissionError."""
    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        raise FileNotFoundError(f"No sandbox found for session {session_id}")
    return sandbox._safe_path(relative_path), os.path.realpath(sandbox.workspace_dir)


async def read_file(session_id: str, path: str) -> str:
    full, _ = _resolve_safe(session_id, path)
    with open(full, "r", encoding="utf-8") as fh:
        return fh.read()


@observe(name="write-file", as_type="span")
async def write_file(session_id: str, path: str, content: str) -> None:
    full, _ = _resolve_safe(session_id, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    langfuse_context.update_current_observation(
        metadata={"file_path": path, "content_length": len(content)}
    )


async def edit_file(session_id: str, path: str, search: str, replace: str) -> None:
    full, _ = _resolve_safe(session_id, path)
    with open(full, "r", encoding="utf-8") as fh:
        content = fh.read()
    if search not in content:
        raise ValueError(f"Search string not found in {path}")
    content = content.replace(search, replace, 1)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)


async def delete_file(session_id: str, path: str) -> None:
    full, _ = _resolve_safe(session_id, path)
    if os.path.isdir(full):
        os.rmdir(full)
    else:
        os.remove(full)


SKIP_DIRS = {"node_modules", ".git", ".next", "dist", ".cache", "__pycache__", ".vite"}


async def list_files(session_id: str, path: str = "/") -> list[FileEntry]:
    full, workspace = _resolve_safe(session_id, path)
    if not os.path.isdir(full):
        raise NotADirectoryError(f"{path} is not a directory")

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
            rel_path = "/" + os.path.relpath(abs_path, workspace)
            is_dir = os.path.isdir(abs_path)
            children = _build_tree(abs_path) if is_dir else None
            entries.append(FileEntry(name=name, path=rel_path, is_directory=is_dir, children=children))
        return entries

    return _build_tree(full)
