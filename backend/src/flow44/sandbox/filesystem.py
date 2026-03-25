from __future__ import annotations

import os
from dataclasses import dataclass

from langfuse.decorators import langfuse_context, observe

from flow44.sandbox.manager import sandbox_manager


@dataclass
class FileEntry:
    name: str
    path: str
    is_directory: bool
    children: list[FileEntry] | None = None


def _resolve_safe(project_id: str, relative_path: str) -> tuple[str, str]:
    """Returns (resolved_path, workspace_root). Raises FileNotFoundError / PermissionError."""
    sandbox = sandbox_manager.get_sandbox(project_id)
    if sandbox is None:
        raise FileNotFoundError(f"No sandbox found for session {project_id}")
    return sandbox._safe_path(relative_path), os.path.realpath(sandbox.workspace_dir)


async def read_file(project_id: str, path: str) -> str:
    full, _ = _resolve_safe(project_id, path)
    with open(full, encoding="utf-8") as fh:  # noqa: ASYNC230
        return fh.read()


@observe(name="write-file", as_type="span")  # type: ignore[untyped-decorator]
async def write_file(project_id: str, path: str, content: str) -> None:
    full, _ = _resolve_safe(project_id, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:  # noqa: ASYNC230
        fh.write(content)
    langfuse_context.update_current_observation(metadata={"file_path": path, "content_length": len(content)})


async def edit_file(project_id: str, path: str, search: str, replace: str) -> None:
    full, _ = _resolve_safe(project_id, path)
    with open(full, encoding="utf-8") as fh:  # noqa: ASYNC230
        content = fh.read()
    if search not in content:
        raise ValueError(f"Search string not found in {path}")
    content = content.replace(search, replace, 1)
    with open(full, "w", encoding="utf-8") as fh:  # noqa: ASYNC230
        fh.write(content)


async def delete_file(project_id: str, path: str) -> None:
    full, _ = _resolve_safe(project_id, path)
    if os.path.isdir(full):  # noqa: ASYNC240
        os.rmdir(full)
    else:
        os.remove(full)


SKIP_DIRS = {"node_modules", ".git", ".next", "dist", ".cache", "__pycache__", ".vite"}


async def list_files(project_id: str, path: str = "/") -> list[FileEntry]:
    full, workspace = _resolve_safe(project_id, path)
    if not os.path.isdir(full):  # noqa: ASYNC240
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
            rel_path = rel_path.replace("\\", "/")
            is_dir = os.path.isdir(abs_path)
            children = _build_tree(abs_path) if is_dir else None
            entries.append(FileEntry(name=name, path=rel_path, is_directory=is_dir, children=children))
        return entries

    return _build_tree(full)
