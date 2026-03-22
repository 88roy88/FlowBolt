from __future__ import annotations

import difflib

from flow44.sandbox.filesystem import read_file, write_file


# TODO: maybe when switching to using git it will be easier to just use git diff for this instead of difflib.
def _make_diff(path: str, old: str, new: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


async def write_file_with_diff(session_id: str, path: str, content: str) -> tuple[str, str]:
    """Write file and return (status_message, diff_string)."""
    try:
        old_content = await read_file(session_id, path)
    except FileNotFoundError:
        old_content = ""

    await write_file(session_id, path, content)

    diff_str = _make_diff(path, old_content, content)
    status = f"OK — wrote {path} ({len(content.splitlines())} lines)"
    return status, diff_str
