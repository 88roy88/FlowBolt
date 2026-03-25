"""Indexed search across sandbox workspace files.

This module maintains a per-project in-memory index to make repeated
"find across files" queries fast without re-reading every file on each request.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

from flow44.sandbox.filesystem import _resolve_safe


SKIP_DIRS = {"node_modules", ".git", ".next", "dist", ".cache", "__pycache__", ".vite"}
DEFAULT_ALLOWED_EXTS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".css",
    ".scss",
    ".sass",
    ".html",
    ".md",
    ".yml",
    ".yaml",
    ".txt",
    ".py",
}


@dataclass
class _IndexedFile:
    path: str
    mtime_ns: int
    size: int
    content: str
    lower: str
    line_starts: list[int]


class _ProjectIndex:
    def __init__(self) -> None:
        self.files: dict[str, _IndexedFile] = {}
        self.overflow: dict[str, tuple[str, str, int, int]] = {}
        self.total_bytes: int = 0
        self.last_built_ts: float = 0.0


_INDEX: dict[str, _ProjectIndex] = {}
_LOCKS: dict[str, asyncio.Lock] = {}


def _get_lock(project_id: str) -> asyncio.Lock:
    lock = _LOCKS.get(project_id)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[project_id] = lock
    return lock


def _rel_path(workspace: str, abs_path: str) -> str:
    rel = "/" + os.path.relpath(abs_path, workspace)
    return rel.replace("\\", "/")


def _build_line_starts(text: str) -> list[int]:
    starts = [0]
    i = 0
    while True:
        j = text.find("\n", i)
        if j == -1:
            break
        starts.append(j + 1)
        i = j + 1
    return starts


def _offset_to_line_col(line_starts: list[int], offset: int) -> tuple[int, int]:
    # 1-based line/col to match Monaco
    lo, hi = 0, len(line_starts) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if line_starts[mid] <= offset:
            lo = mid + 1
        else:
            hi = mid - 1
    line_idx = max(0, hi)
    line_number = line_idx + 1
    col = (offset - line_starts[line_idx]) + 1
    return line_number, col


def _iter_files(workspace: str) -> list[tuple[str, str, int, int]]:
    out: list[tuple[str, str, int, int]] = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if (not d.startswith(".")) and d not in SKIP_DIRS]
        for name in files:
            if name.startswith("."):
                continue
            abs_path = os.path.join(root, name)
            try:
                st = os.stat(abs_path)
            except OSError:
                continue
            rel = _rel_path(workspace, abs_path)
            out.append((rel, abs_path, getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)), st.st_size))
    return out


async def _read_text(abs_path: str, max_bytes: int) -> str | None:
    def _read() -> str | None:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                data = fh.read(max_bytes + 1)
                if len(data) > max_bytes:
                    return None
                return data
        except OSError:
            return None

    return await asyncio.to_thread(_read)


async def ensure_index(
    project_id: str,
    *,
    allowed_exts: set[str] | None = None,
    max_total_bytes: int = 80_000_000,
    max_file_bytes: int = 5_000_000,
    stale_after_s: float = 3.0,
) -> _ProjectIndex:
    lock = _get_lock(project_id)
    async with lock:
        idx = _INDEX.get(project_id)
        now = time.time()
        if idx is not None and (now - idx.last_built_ts) < stale_after_s:
            return idx

        workspace_path, _ = _resolve_safe(project_id, "/")
        workspace = os.path.realpath(workspace_path)
        exts = allowed_exts or DEFAULT_ALLOWED_EXTS

        if idx is None:
            idx = _ProjectIndex()
            _INDEX[project_id] = idx

        seen: set[str] = set()
        candidates = _iter_files(workspace)
        for rel, abs_path, mtime_ns, size in candidates:
            seen.add(rel)
            ext = os.path.splitext(rel)[1].lower()
            if ext and ext not in exts:
                continue
            prev = idx.files.get(rel)
            if prev and prev.mtime_ns == mtime_ns and prev.size == size:
                continue

            prev_overflow = idx.overflow.get(rel)
            if prev_overflow and prev_overflow[2] == mtime_ns and prev_overflow[3] == size:
                continue

            content = await _read_text(abs_path, max_file_bytes)
            if content is None:
                # Too large; keep as overflow and scan on-demand.
                if prev:
                    idx.total_bytes -= len(prev.content.encode("utf-8", errors="ignore"))
                    idx.files.pop(rel, None)
                idx.overflow[rel] = (rel, abs_path, mtime_ns, size)
                continue

            content_bytes = len(content.encode("utf-8", errors="ignore"))
            if idx.total_bytes + content_bytes > max_total_bytes:
                # Budget exceeded; keep as overflow and scan on-demand.
                if prev:
                    idx.total_bytes -= len(prev.content.encode("utf-8", errors="ignore"))
                    idx.files.pop(rel, None)
                idx.overflow[rel] = (rel, abs_path, mtime_ns, size)
                continue

            if prev:
                idx.total_bytes -= len(prev.content.encode("utf-8", errors="ignore"))
            idx.overflow.pop(rel, None)

            idx.files[rel] = _IndexedFile(
                path=rel,
                mtime_ns=mtime_ns,
                size=size,
                content=content,
                lower=content.lower(),
                line_starts=_build_line_starts(content),
            )
            idx.total_bytes += content_bytes

        # Remove deleted files
        for rel in list(idx.files.keys()):
            if rel not in seen:
                v = idx.files.pop(rel)
                idx.total_bytes -= len(v.content.encode("utf-8", errors="ignore"))
        for rel in list(idx.overflow.keys()):
            if rel not in seen:
                idx.overflow.pop(rel, None)

        idx.last_built_ts = now
        return idx


async def search_across_files(
    project_id: str,
    query: str,
    *,
    case_sensitive: bool = False,
    max_results: int = 2000,
    max_hits_per_file: int = 200,
    allowed_exts: set[str] | None = None,
) -> list[dict[str, Any]]:
    q = query.strip()
    if not q:
        return []

    idx = await ensure_index(project_id, allowed_exts=allowed_exts)

    needle = q if case_sensitive else q.lower()
    out: list[dict[str, Any]] = []
    total = 0

    for rel, file_index in idx.files.items():
        hay = file_index.content if case_sensitive else file_index.lower
        hits: list[dict[str, Any]] = []
        from_idx = 0
        while True:
            pos = hay.find(needle, from_idx)
            if pos == -1:
                break
            line, col = _offset_to_line_col(file_index.line_starts, pos)
            line_start = file_index.line_starts[line - 1]
            line_end = file_index.content.find("\n", pos)
            if line_end == -1:
                line_end = len(file_index.content)
            preview = file_index.content[line_start:line_end].strip()
            hits.append({"line": line, "column": col, "preview": preview[:240]})
            total += 1
            if total >= max_results or len(hits) >= max_hits_per_file:
                break
            from_idx = pos + max(1, len(needle))

        if hits:
            out.append({"path": rel, "uri": f"file://{rel}", "hits": hits})

        if total >= max_results:
            break

    if total < max_results and idx.overflow:
        for rel, (_rel, abs_path, _mtime_ns, _size) in idx.overflow.items():
            if total >= max_results:
                break
            remaining = max_results - total
            if remaining <= 0:
                break
            hits = await _search_overflow_file(
                abs_path,
                needle,
                case_sensitive=case_sensitive,
                max_hits=min(max_hits_per_file, remaining),
            )
            if hits:
                out.append({"path": rel, "uri": f"file://{rel}", "hits": hits})
                total += len(hits)
                if total >= max_results:
                    break

    return out


async def _search_overflow_file(
    abs_path: str,
    needle: str,
    *,
    case_sensitive: bool,
    max_hits: int,
) -> list[dict[str, Any]]:
    def _run() -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                for line_no, line in enumerate(fh, start=1):
                    hay = line if case_sensitive else line.lower()
                    from_idx = 0
                    while True:
                        pos = hay.find(needle, from_idx)
                        if pos == -1:
                            break
                        hits.append({"line": line_no, "column": pos + 1, "preview": line.strip()[:240]})
                        if len(hits) >= max_hits:
                            return hits
                        from_idx = pos + max(1, len(needle))
        except OSError:
            return hits
        return hits

    return await asyncio.to_thread(_run)
