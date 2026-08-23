from __future__ import annotations

import asyncio
import subprocess

from flow44.sandbox.base import workspace_path

_GIT_NAME = "BuildApp AI"
_GIT_EMAIL = "ai@buildapp.local"


class GitError(RuntimeError):
    pass


class Git:
    def __init__(self, project_id: str) -> None:
        self.workspace_dir = workspace_path(project_id)

    async def _run(self, *args: str) -> str:
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
            raise GitError(f"git {' '.join(args)} ({result.returncode}): {result.stderr.strip()}")
        return result.stdout.strip()

    async def _succeeds(self, *args: str) -> bool:
        try:
            await self._run(*args)
            return True
        except GitError:
            return False

    # -- Queries --

    async def is_repo(self) -> bool:
        # `--git-dir` is `.git` only for a workspace-local repo; an ancestor repo yields an abs path.
        try:
            return await self._run("rev-parse", "--git-dir") in (".git", ".git/")
        except GitError:
            return False

    async def is_detached(self) -> bool:
        # `symbolic-ref -q HEAD` fails when detached — and on a non-repo too, hence the is_repo check.
        return await self.is_repo() and not await self._succeeds("symbolic-ref", "-q", "HEAD")

    async def head_sha(self) -> str:
        return await self._run("rev-parse", "HEAD")

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
        if not await self._run("status", "--porcelain"):
            return None
        await self._run("commit", "-m", message)
        return await self.head_sha()

    async def checkout(self, sha: str) -> None:
        await self._run("checkout", "-f", "--detach", sha)

    async def checkout_latest(self) -> None:
        await self._run("checkout", "-f", "main")

    async def restore_main(self, sha: str) -> None:
        # One command: a separate checkout can fail and leave `main` ahead, silently un-restoring later.
        await self._run("checkout", "-f", "-B", "main", sha)
