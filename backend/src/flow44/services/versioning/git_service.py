from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)


_GIT_NAME = "BuildApp AI"
_GIT_EMAIL = "ai@buildapp.local"

# Message via file: subprocess escapes inner quotes as \", which cmd.exe can't parse, so -m mangles it.
_MSG_FILE = ".git/COMMIT_BUILDAPP_MSG"

# A full git commit hash (sha-1: 40 hex; sha-256 repos: 64).
_SHA_RE = re.compile(r"[0-9a-f]{40,64}")


# exec() exposes no exit code, so these parse git's porcelain output.
def _extract_sha(output: str) -> str:
    for line in output.splitlines():
        candidate = line.strip()
        if _SHA_RE.fullmatch(candidate):
            return candidate
    return ""


def _first_int(output: str) -> int:
    for line in output.splitlines():
        candidate = line.strip()
        if candidate.isdigit():
            return int(candidate)
    return 0


class GitService:
    def __init__(self, sandbox: PnpmSandbox) -> None:
        self.sandbox = sandbox

    async def _run(self, args: str) -> str:
        # `2>&1`: the Windows sandbox yields only stdout, so fold in git's stderr.
        lines: list[str] = []
        async for line in self.sandbox.exec(f"git {args} 2>&1"):
            lines.append(line)
        return "".join(lines).strip()

    # -- Queries --

    async def is_repo(self) -> bool:
        # `--git-dir` is `.git` only for a workspace-local repo; an ancestor repo yields an abs path.
        out = await self._run("rev-parse --git-dir")
        return any(line.strip() in (".git", ".git/") for line in out.splitlines())

    async def head_sha(self) -> str:
        return _extract_sha(await self._run("rev-parse HEAD"))

    async def current_is_detached(self) -> bool:
        # `symbolic-ref -q HEAD` prints the branch ref when attached, nothing when detached.
        out = await self._run("symbolic-ref -q HEAD")
        return "refs/heads/" not in out

    async def commit_count(self) -> int:
        return _first_int(await self._run("rev-list --count HEAD"))

    # -- Mutations --

    async def init(self, initial_message: str) -> str | None:
        await self._run("init")
        # Set `main` before the first commit without depending on git >= 2.28 (`init -b`).
        await self._run("symbolic-ref HEAD refs/heads/main")
        await self._run(f'config user.name "{_GIT_NAME}"')
        await self._run(f'config user.email "{_GIT_EMAIL}"')
        return await self.commit_all(initial_message)

    async def commit_all(self, message: str) -> str | None:
        await self._run("add -A")
        if not (await self._run("status --porcelain")).strip():
            return None
        head_before = await self.head_sha()
        await self.sandbox.write_file(_MSG_FILE, message)
        await self._run(f"commit -F {_MSG_FILE}")
        sha = await self.head_sha()
        if sha == head_before:
            logger.warning("[git] commit did not advance HEAD; version is unrecorded")
            return None
        return sha

    async def checkout(self, sha: str) -> None:
        await self._run(f"checkout -f --detach {sha}")

    async def checkout_latest(self) -> None:
        await self._run("checkout -f main")

    async def reset_hard(self, sha: str) -> None:
        await self._run("checkout -f main")
        await self._run(f"reset --hard {sha}")
