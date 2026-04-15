import os
import shutil
from abc import ABC
from pathlib import PurePosixPath

from pydantic import BaseModel

from flow44.sandbox.base import BaseSandbox
from flow44.sandbox.constants import SKIP_DIRS


class FileEntry(BaseModel):
    name: str
    path: str
    is_directory: bool
    children: list["FileEntry"] | None = None


class FileSystemMixin(BaseSandbox, ABC):
    async def read_file(self, path: str) -> str:
        full = self._safe_path(path)
        with open(full, encoding="utf-8") as f:  # noqa: ASYNC230
            return f.read()

    async def write_file(self, path: str, content: str) -> None:
        full = self._safe_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            f.write(content)

    async def write_binary_file(self, path: str, content: bytes) -> None:
        full = self._safe_path(path)
        if os.path.exists(full):  # noqa: ASYNC240
            raise FileExistsError(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "xb") as f:  # noqa: ASYNC230
            f.write(content)

    async def create_file(self, path: str, content: str = "") -> None:
        full = self._safe_path(path)
        if os.path.exists(full):  # noqa: ASYNC240
            raise FileExistsError(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "x", encoding="utf-8") as f:  # noqa: ASYNC230
            f.write(content)

    async def rename_path(self, source_path: str, destination_path: str) -> None:
        source_full = self._safe_path(source_path)
        destination_full = self._safe_path(destination_path)
        if not os.path.exists(source_full):  # noqa: ASYNC240
            raise FileNotFoundError(source_path)
        if os.path.exists(destination_full):  # noqa: ASYNC240
            raise FileExistsError(destination_path)
        os.makedirs(os.path.dirname(destination_full), exist_ok=True)
        os.replace(source_full, destination_full)

    async def edit_file(self, path: str, search: str, replace: str) -> None:
        full = self._safe_path(path)
        with open(full, encoding="utf-8") as fh:  # noqa: ASYNC230
            content = fh.read()
        if search not in content:
            raise ValueError(f"Search string not found in {path}")
        content = content.replace(search, replace, 1)
        with open(full, "w", encoding="utf-8") as fh:  # noqa: ASYNC230
            fh.write(content)

    async def delete_file(self, path: str) -> None:
        full = self._safe_path(path)
        if os.path.isdir(full):  # noqa: ASYNC240
            shutil.rmtree(full)
        else:
            os.remove(full)

    async def list_files(self, path: str = "/") -> list[FileEntry]:
        full = self._safe_path(path)
        workspace = os.path.realpath(self.workspace_dir)  # noqa: ASYNC240
        if not os.path.isdir(full):  # noqa: ASYNC240
            raise NotADirectoryError(f"{path} is not a directory")

        # Review TODO: is this only for the representation of the tree? If so we can create
        # a util file for those stuff, read file format (with line number) grep and glob as well.
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
                rel_path = "/" + PurePosixPath(os.path.relpath(abs_path, workspace)).as_posix()
                is_dir = os.path.isdir(abs_path)
                children = _build_tree(abs_path) if is_dir else None
                entries.append(FileEntry(name=name, path=rel_path, is_directory=is_dir, children=children))
            return entries

        return _build_tree(full)
