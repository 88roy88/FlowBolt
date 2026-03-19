from __future__ import annotations

from app.sandbox.filesystem import edit_file, read_file
from app.ai.tools.write_file import _make_diff


async def edit_file_with_context(session_id: str, path: str, search: str, replace: str) -> tuple[str, str]:
    """Edit file with search/replace. Returns (status_message, diff_string).

    On failure, returns error message with current file content for retry.
    """
    try:
        current = await read_file(session_id, path)
    except FileNotFoundError:
        return f"Error: File not found: {path}", ""

    try:
        await edit_file(session_id, path, search, replace)
    except ValueError:
        lines = current.splitlines()
        snippet = "\n".join(lines[:40])
        if len(lines) > 40:
            snippet += f"\n... ({len(lines)} lines total)"
        return (
            f"Error: search string not found in {path}. "
            f"The search must match the file exactly (including whitespace).\n\n"
            f"Current file content:\n```\n{snippet}\n```"
        ), ""

    new_content = await read_file(session_id, path)
    diff_str = _make_diff(path, current, new_content)
    return f"OK — edited {path}", diff_str
