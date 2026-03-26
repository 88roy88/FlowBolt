import asyncio
import os
from abc import ABC
from pathlib import Path

from pydantic import BaseModel

from flow44.sandbox.base import BaseSandbox

# Review TODO: This feels like we have it in 10 diffrent places, lets have a utils with it.
_GLOB_SKIP_DIRS = {"node_modules", ".git", "dist", ".next", ".cache", "__pycache__"}
_GREP_SKIP_GLOBS = [
    "!node_modules",
    "!.git",
    "!dist",
    "!.next",
    "!pnpm-lock.yaml",
    "!package-lock.json",
    "!yarn.lock",
    "!bun.lockb",
    "!Cargo.lock",
    "!poetry.lock",
    "!Gemfile.lock",
    "!composer.lock",
    "!.cache",
    "!__pycache__",
]


class GrepMatch(BaseModel):
    # Review TODO: replace with Path?
    file: str  # workspace-relative path, prefixed with "/"
    line: int
    content: str
    column: int | None = None  # Optional column position (1-indexed)


class SearchMatch(BaseModel):
    # Review TODO: replace with Path?
    file: str
    line: int
    column: int
    preview: str


# TODO: think if this should inherit from FileSystemMixin.
class SearchMixin(BaseSandbox, ABC):
    async def glob(self, pattern: str) -> list[str]:
        workspace = Path(os.path.realpath(self.workspace_dir))  # noqa: ASYNC240
        results = []
        for p in workspace.glob(pattern):  # noqa: ASYNC240
            if any(part in _GLOB_SKIP_DIRS for part in p.parts):
                continue
            results.append("/" + str(p.relative_to(workspace)))
            if len(results) >= 100:
                break
        return sorted(results)

    # TODO: take a look at the grep.py in code-validation-service for reference
    async def grep(  # noqa: C901, PLR0912, PLR0913
        self,
        pattern: str,
        path: str = "/",
        file_pattern: str | None = None,
        max_results: int | None = None,
        with_column: bool = False,  # Include column positions
        case_sensitive: bool = True,  # Case sensitivity (default true for ripgrep)
        word_match: bool = False,  # Match whole words only
        fixed_strings: bool = False,  # Treat pattern as literal string (not regex)
    ) -> list[GrepMatch]:
        workspace = os.path.realpath(self.workspace_dir)  # noqa: ASYNC240
        search_path = self._safe_path(path)  # raises PermissionError on traversal

        cmd = ["rg", "--no-heading", "--line-number"]
        if with_column:
            cmd.append("--column")  # Add column numbers to output
        if not case_sensitive:
            cmd.append("--ignore-case")  # -i flag for case-insensitive search
        if word_match:
            cmd.append("--word-regexp")  # -w flag for whole word matching
        if fixed_strings:
            cmd.append("--fixed-strings")  # -F flag for literal string search (not regex)
        for skip in _GREP_SKIP_GLOBS:
            cmd.extend(["--glob", skip])
        if max_results is not None:
            cmd.extend(["--max-count", str(max_results)])
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        cmd.extend([pattern, search_path])

        try:
            # Review TODO: why not use sansbox exec
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        except TimeoutError:
            return []
        except FileNotFoundError:
            return []

        output = stdout.decode("utf-8", errors="replace")
        matches: list[GrepMatch] = []
        for raw_line in output.splitlines():
            # rg output: /abs/workspace/path/to/file:42:content (without --column)
            # rg output: /abs/workspace/path/to/file:42:10:content (with --column)
            if raw_line.startswith(workspace):
                raw_line = raw_line[len(workspace) :]  # noqa: PLW2901

            if with_column:
                # Format: /relative/path:42:10:content
                parts = raw_line.split(":", 3)
                if len(parts) < 4:
                    continue
                file_path, line_str, col_str, content = parts
                try:
                    line_num = int(line_str)
                    col_num = int(col_str)
                except ValueError:
                    continue
            else:
                # Format: /relative/path:42:content
                parts = raw_line.split(":", 2)
                if len(parts) < 3:
                    continue
                file_path, line_str, content = parts
                try:
                    line_num = int(line_str)
                except ValueError:
                    continue
                col_num = None

            # Ensure consistent path format: always start with "/"
            # This matches frontend expectations and file tree format
            if not file_path.startswith("/"):
                file_path = "/" + file_path

            matches.append(GrepMatch(file=file_path, line=line_num, content=content, column=col_num))
        return matches
