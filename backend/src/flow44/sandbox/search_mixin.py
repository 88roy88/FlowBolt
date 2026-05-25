import json
import logging
import os
import shlex
import shutil
import subprocess
from abc import ABC
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from flow44.sandbox.base import BaseSandbox
from flow44.sandbox.constants import GREP_SKIP_GLOBS, SKIP_DIRS

logger = logging.getLogger(__name__)


class SearchToolError(RuntimeError):
    """Raised when the underlying search tool cannot execute correctly."""


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

    @staticmethod
    def _build_grep_args(
        pattern: str,
        rel_search: str,
        file_pattern: str | None,
        max_results: int | None,
        case_sensitive: bool,
        word_match: bool,
        fixed_strings: bool,
    ) -> list[str]:
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
        return args

    @staticmethod
    def _parse_grep_json_output(output: str, with_column: bool) -> list[GrepMatch]:
        matches: list[GrepMatch] = []
        has_valid_json = False

        for raw_line in output.splitlines():
            try:
                msg = json.loads(raw_line)
                has_valid_json = True
            except json.JSONDecodeError:
                # Log non-JSON lines as they might indicate errors
                if raw_line.strip() and not has_valid_json:
                    logger.warning("Ripgrep output is not valid JSON, possible error: %s", raw_line[:200])
                continue
            if msg.get("type") != "match":
                continue
            data = msg.get("data", {})
            file_path = "/" + PurePosixPath(data["path"]["text"]).as_posix().lstrip("/")
            line_num = data["line_number"]
            content = data["lines"]["text"].rstrip("\n")
            col_num = data["submatches"][0]["start"] + 1 if with_column and data.get("submatches") else None
            matches.append(GrepMatch(file=file_path, line=line_num, content=content, column=col_num))

        # If we got output but no valid JSON, ripgrep likely failed
        if output.strip() and not has_valid_json:
            logger.error("Ripgrep failed. Full output: %s", output[:500])
            raise SearchToolError("Ripgrep returned invalid output")

        return matches

    async def _run_search_command(self, cmd: str) -> str:
        try:
            lines: list[str] = []
            async for line in self.exec(cmd):
                lines.append(line)
        except Exception as e:
            logger.warning("Failed to execute ripgrep command: %s", e, exc_info=True)
            raise SearchToolError(f"Failed to execute ripgrep command: {e}") from e
        return "".join(lines)

    # TODO: take a look at the grep.py in code-validation-service for reference
    async def grep(  # noqa: PLR0913
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
        if shutil.which("rg") is None:
            raise SearchToolError("ripgrep (rg) is required for search but was not found in PATH")

        # Validate path (raises PermissionError on traversal); compute workspace-relative search path
        abs_search = self._safe_path(path)
        rel_search = PurePosixPath(os.path.relpath(abs_search, self.workspace_dir)).as_posix()  # noqa: ASYNC240

        args = self._build_grep_args(
            pattern=pattern,
            rel_search=rel_search,
            file_pattern=file_pattern,
            max_results=max_results,
            case_sensitive=case_sensitive,
            word_match=word_match,
            fixed_strings=fixed_strings,
        )

        if os.name == "nt":  # noqa: SIM108
            cmd = subprocess.list2cmdline(args)
        else:
            cmd = " ".join(shlex.quote(a) for a in args)
        output = await self._run_search_command(cmd)
        return self._parse_grep_json_output(output, with_column=with_column)
