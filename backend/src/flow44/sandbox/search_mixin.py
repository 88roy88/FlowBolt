import json
import os
import shlex
from abc import ABC
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from flow44.sandbox.base import BaseSandbox
from flow44.sandbox.constants import GREP_SKIP_GLOBS, SKIP_DIRS


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
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            # PurePosixPath.as_posix() normalises backslashes on Windows
            results.append("/" + PurePosixPath(p.relative_to(workspace)).as_posix())
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
        with_column: bool = False,
        case_sensitive: bool = True,
        word_match: bool = False,
        fixed_strings: bool = False,
    ) -> list[GrepMatch]:
        # Validate path (raises PermissionError on traversal); compute workspace-relative search path
        abs_search = self._safe_path(path)
        rel_search = PurePosixPath(os.path.relpath(abs_search, self.workspace_dir)).as_posix()  # noqa: ASYNC240

        # --json gives structured output: no colon-splitting, no drive-letter ambiguity on Windows
        args: list[str] = ["rg", "--json"]
        if not case_sensitive:
            args.append("--ignore-case")
        if word_match:
            args.append("--word-regexp")
        if fixed_strings:
            args.append("--fixed-strings")
        for skip in GREP_SKIP_GLOBS:
            args.extend(["--glob", skip])
        if max_results is not None:
            args.extend(["--max-count", str(max_results)])
        if file_pattern:
            args.extend(["--glob", file_pattern])
        args.extend([pattern, rel_search])

        # Run via self.exec() so rg runs inside the sandbox environment (nsjail, Windows cmd, etc.)
        # and outputs workspace-relative paths — no absolute path stripping, no drive-letter issues.
        cmd = " ".join(shlex.quote(a) for a in args)
        try:
            lines: list[str] = []
            async for line in self.exec(cmd):
                lines.append(line)
        except Exception:
            return []

        matches: list[GrepMatch] = []
        for raw_line in "".join(lines).splitlines():
            try:
                msg = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if msg.get("type") != "match":
                continue
            data = msg.get("data", {})
            file_path = "/" + PurePosixPath(data["path"]["text"]).as_posix().lstrip("/")
            line_num = data["line_number"]
            content = data["lines"]["text"].rstrip("\n")
            col_num = data["submatches"][0]["start"] + 1 if with_column and data.get("submatches") else None
            matches.append(GrepMatch(file=file_path, line=line_num, content=content, column=col_num))
        return matches
