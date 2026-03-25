import re
from pathlib import PurePath

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Vite error banner:  [vite] error ... or  ERROR  ...
_VITE_ERROR_START = re.compile(r"\[vite\].*(?:error|ERROR)|ERROR\s+")

# TypeScript-style:  src/App.tsx(12,5): error TS2304: ...
_TS_ERROR = re.compile(r"(?P<file>[^\s(]+)\((?P<line>\d+),(?P<col>\d+)\):\s*error\s+\w+:\s*(?P<msg>.+)")

# Vite / esbuild / SWC:  /path/to/file.tsx:12:5
_FILE_LINE_COL = re.compile(r"(?P<file>/[^\s:]+\.\w+):(?P<line>\d+):(?P<col>\d+)")

# Vite internal server error:  /path/to/file.tsx: Message. (12:5)
_VITE_INTERNAL = re.compile(r"(?P<file>/\S+\.(?:tsx?|jsx?|css|html)):\s*(?P<msg>.+?)\s*\((?P<line>\d+):(?P<col>\d+)\)")

# Fallback
_GENERIC_ERROR = re.compile(r"(?:error|Error|ERROR)[:\s]")

# Lines to ignore — npm notices, update warnings, etc.
_IGNORE_PATTERNS = [
    re.compile(r"npm notice", re.IGNORECASE),
    re.compile(r"npm warn", re.IGNORECASE),
    re.compile(r"New (?:major|minor|patch) version of npm available"),
    re.compile(r"Run `npm install -g npm"),
    re.compile(r"Update available!"),
    re.compile(r"Corepack is about to download"),
    re.compile(r"pnpm approve-builds"),
    re.compile(r"\[vite\] failed to connect to websocket"),
]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


class BuildError(BaseModel):
    model_config = {"frozen": True}

    source: str = "build"
    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None

    def __hash__(self) -> int:
        return hash((self.file, self.line))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BuildError):
            return NotImplemented
        return self.file == other.file and self.line == other.line


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _is_user_source(path: str) -> bool:
    """Return True if path looks like a user source file (not node_modules or partial)."""
    parts = PurePath(path).parts
    return "src" in parts and "node_modules" not in parts


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def should_ignore(line: str) -> bool:
    """Return True if this line is noise (npm notices, update warnings, etc.)."""
    return any(p.search(line) for p in _IGNORE_PATTERNS)


def is_error_line(clean_line: str) -> bool:
    """Return True if this line looks like it contains a build error."""
    return bool(
        _VITE_ERROR_START.search(clean_line)
        or _TS_ERROR.search(clean_line)
        or (_GENERIC_ERROR.search(clean_line) and _FILE_LINE_COL.search(clean_line))
    )


def parse_error_block(block: str) -> BuildError | None:
    """Extract structured error info from a block of log text."""
    # Try TS-style first
    m = _TS_ERROR.search(block)
    if m:
        return BuildError(
            source="build",
            message=m.group("msg").strip(),
            file=m.group("file"),
            line=int(m.group("line")),
            column=int(m.group("col")),
        )

    # Try Vite internal server error:  /path/file.tsx: Msg. (line:col)
    m = _VITE_INTERNAL.search(block)
    if m:
        fpath = m.group("file")
        return BuildError(
            message=m.group("msg").strip(),
            file=fpath if _is_user_source(fpath) else None,
            line=int(m.group("line")) if _is_user_source(fpath) else None,
            column=int(m.group("col")) if _is_user_source(fpath) else None,
        )

    # Try file:line:col style — only extract file if it's user source
    for m in _FILE_LINE_COL.finditer(block):
        fpath = m.group("file")
        if _is_user_source(fpath):
            msg_lines = []
            for line in block.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("at ") and not _FILE_LINE_COL.match(stripped):
                    msg_lines.append(stripped)
            message = " ".join(msg_lines[:3]) if msg_lines else block.strip()[:200]
            return BuildError(
                message=message,
                file=fpath,
                line=int(m.group("line")),
                column=int(m.group("col")),
            )

    # Fallback: generic error
    first_line = block.strip().splitlines()[0] if block.strip() else block
    return BuildError(
        source="build",
        message=first_line.strip()[:300],
    )
