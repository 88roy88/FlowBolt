from __future__ import annotations

import os
from pathlib import Path

# TODO: add support to gitignore instead of the hardcoded skip list
SKIP_DIRS = {"node_modules", ".git", "dist", ".next", ".cache", "__pycache__"}


async def glob(session_id: str, pattern: str) -> str:
    from flow44.sandbox.manager import sandbox_manager

    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        return "Error: No sandbox found"

    workspace = Path(os.path.realpath(sandbox.workspace_dir))

    results = []
    for p in workspace.glob(pattern):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = "/" + str(p.relative_to(workspace))
        results.append(rel)
        if len(results) >= 100:
            break

    if not results:
        return "No files found matching pattern."
    return "\n".join(sorted(results))
