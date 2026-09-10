from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from flow44.ai.agents.file_diffs import FileDiff
from flow44.sandbox.base import workspace_path

_GIT_NAME = "BuildApp AI"
_GIT_EMAIL = "ai@buildapp.local"


class GitError(RuntimeError):
    pass


def _split_file_diffs(show_output: str) -> list[FileDiff]:
    diffs = []
    for chunk in f"\n{show_output}".split("\ndiff --git ")[1:]:
        meta, marker, body = chunk.partition("\n--- ")
        if not marker:
            continue
        header, _, modes = meta.partition("\n")
        path = header.removeprefix("a/").partition(" b/")[0]
        diffs.append(FileDiff(path=path, diff=f"--- {body}", is_new="new file mode " in modes))
    return diffs


class Git:
    def __init__(self, project_id: str) -> None:
        self.workspace_dir = workspace_path(project_id)
        self.git_dir = os.path.join(self.workspace_dir, ".git")

    async def _run(self, *args: str) -> str:
        # Pin the git dir: under bare `-C`, a workspace with no `.git` walks up and finds FlowBolt's repo.
        repo = ["-C", self.workspace_dir, "--git-dir", self.git_dir, "--work-tree", self.workspace_dir]
        # to_thread, not create_subprocess_exec: uvicorn's Windows selector loop has no subprocess support.
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", *repo, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode:
            raise GitError(f"git {' '.join(args)} ({result.returncode}): {result.stderr.strip()}")
        return result.stdout.strip()

    # -- Queries --

    def _head(self) -> str | None:
        try:
            return Path(self.git_dir, "HEAD").read_text()
        except OSError:
            return None

    def is_repo(self) -> bool:
        return self._head() is not None

    def is_detached(self) -> bool:
        head = self._head()
        return head is not None and not head.startswith("ref:")

    async def head_sha(self) -> str:
        return await self._run("rev-parse", "HEAD")

    async def is_dirty(self) -> bool:
        return bool(await self._run("status", "--porcelain"))

    async def changed_files(self) -> list[str]:
        tracked = await self._run("diff", "--name-only", "HEAD")
        untracked = await self._run("ls-files", "--others", "--exclude-standard")
        return sorted({*tracked.splitlines(), *untracked.splitlines()} - {""})

    async def commit_diffs(self, sha: str, *, max_chars: int) -> list[FileDiff]:
        out = await self._run("show", "--format=", "--no-color", sha)
        if len(out) > max_chars:
            return []
        return _split_file_diffs(out)

    # -- Mutations --

    async def init(self, message: str) -> str | None:
        await self._run("init")
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
        await self._run("checkout", "-f", "-B", "main", sha)

    async def discard_all(self) -> None:
        await self._run("reset", "--hard", "HEAD")
        await self._run("clean", "-fd")
