from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)


_GIT_NAME = "BuildApp AI"
_GIT_EMAIL = "ai@buildapp.local"


class Git:
    def __init__(self, sandbox: PnpmSandbox) -> None:
        self.workspace_dir = sandbox.workspace_dir

    async def _run(self, *args: str) -> tuple[int, str]:
        # Thread, not create_subprocess_exec: uvicorn runs a Windows selector loop, which has no subprocess support.
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", self.workspace_dir, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode:
            logger.debug("[git] %s failed (%s): %s", args[0], result.returncode, result.stderr.strip())
        return result.returncode, result.stdout.strip()

    async def _succeeds(self, *args: str) -> bool:
        code, _ = await self._run(*args)
        return code == 0

    # -- Queries --

    async def is_repo(self) -> bool:
        # `--git-dir` is `.git` only for a workspace-local repo; an ancestor repo yields an abs path.
        code, out = await self._run("rev-parse", "--git-dir")
        return code == 0 and out in (".git", ".git/")

    async def is_detached(self) -> bool:
        # `symbolic-ref -q HEAD` fails when detached — and on a non-repo too, hence the is_repo check.
        return await self.is_repo() and not await self._succeeds("symbolic-ref", "-q", "HEAD")

    async def head_sha(self) -> str:
        _, out = await self._run("rev-parse", "HEAD")
        return out

    # -- Mutations --

    async def init(self, message: str) -> str | None:
        await self._run("init")
        # Set `main` before the first commit without depending on git >= 2.28 (`init -b`).
        await self._run("symbolic-ref", "HEAD", "refs/heads/main")
        await self._run("config", "user.name", _GIT_NAME)
        await self._run("config", "user.email", _GIT_EMAIL)
        return await self.commit_all(message)

    async def commit_all(self, message: str) -> str | None:
        await self._run("add", "-A")
        if not await self._succeeds("commit", "-m", message):
            return None
        return await self.head_sha()

    async def checkout(self, sha: str) -> None:
        await self._run("checkout", "-f", "--detach", sha)

    async def checkout_latest(self) -> None:
        await self._run("checkout", "-f", "main")

    async def reset_hard(self, sha: str) -> None:
        # Everything ahead of `sha` stays recoverable via reflog.
        await self.checkout_latest()
        await self._run("reset", "--hard", sha)
