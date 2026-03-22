from __future__ import annotations

import asyncio
import os


async def grep(
    session_id: str,
    pattern: str,
    path: str = "/",
    file_pattern: str | None = None,
) -> str:
    from flow44.sandbox.manager import sandbox_manager

    sandbox = sandbox_manager.get_sandbox(session_id)
    if sandbox is None:
        return "Error: No sandbox found"

    workspace = os.path.realpath(sandbox.workspace_dir)
    search_path = os.path.realpath(os.path.join(workspace, path.lstrip("/")))

    if not search_path.startswith(workspace):
        return "Error: Path traversal detected"

    # TODO: add rg to the docker
    # TODO: make number of context line and number of results configurable.
    # TODO: add support to gitignore instead of the hardcoded skip list
    cmd = [
        "rg",
        "--no-heading",
        "--line-number",
        "--max-count",
        "50",
        "--glob",
        "!node_modules",
        "--glob",
        "!.git",
        "--glob",
        "!dist",
        "--glob",
        "!.next",
    ]
    if file_pattern:
        cmd.extend(["--glob", file_pattern])
    cmd.extend([pattern, search_path])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        output = stdout.decode("utf-8", errors="replace")

        lines = []
        for line in output.splitlines()[:50]:
            if line.startswith(workspace):
                line = line[len(workspace) :]
            lines.append(line)

        if not lines:
            return "No matches found."
        return "\n".join(lines)
    except TimeoutError:
        return "Error: grep timed out"
    except FileNotFoundError:
        return "Error: ripgrep (rg) not available"
