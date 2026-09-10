import asyncio
from pathlib import Path

import pytest

from flow44.config import settings
from flow44.services.versioning.git import Git, GitError

from .conftest import VersionChain, git_out, outer_repo, requires_git

pytestmark = requires_git


async def test_changed_files_include_dirty_and_untracked_but_not_ignored(repo: Git, workspace: Path) -> None:
    (workspace / ".gitignore").write_text("node_modules\n")
    await repo.commit_all("ignore dependencies")
    (workspace / "a.txt").write_text("changed")
    (workspace / "new.txt").write_text("added")
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "dep.js").write_text("noise")

    assert await repo.is_dirty()
    assert await repo.changed_files() == ["a.txt", "new.txt"]


async def test_operations_cannot_reach_an_enclosing_repo(project_id: str, workspace: Path, tmp_path: Path) -> None:
    outer_head = outer_repo(tmp_path)
    git = Git(project_id)

    assert git.is_repo() is False
    assert git.is_detached() is False

    operations = [
        git.head_sha,
        git.is_dirty,
        git.changed_files,
        git.checkout_latest,
        lambda: git.commit_all("must never reach the enclosing repo"),
        lambda: git.checkout("HEAD"),
        lambda: git.restore_main("HEAD"),
    ]
    for operation in operations:
        with pytest.raises(GitError):
            await operation()

    assert git_out(tmp_path, "rev-parse", "HEAD") == outer_head
    assert git_out(tmp_path, "status", "--porcelain") == ""
    assert (tmp_path / "sentinel.txt").read_text() == "outer"


async def test_init_adopts_a_half_built_git_directory(project_id: str, workspace: Path, tmp_path: Path) -> None:
    outer_repo(tmp_path)
    (workspace / "a.txt").write_text("x")
    (workspace / ".git" / "objects").mkdir(parents=True)
    git = Git(project_id)

    assert git.is_repo() is False
    assert await git.init("v0")
    assert git.is_repo() is True


async def test_commit_diffs_reports_one_hunk_set_per_file(repo: Git, workspace: Path) -> None:
    (workspace / "a.txt").write_text("changed\n")
    (workspace / "new.txt").write_text("added\n")
    sha = await repo.commit_all("edits")
    assert sha

    diffs = await repo.commit_diffs(sha, max_chars=10_000)

    assert {d.path: d.is_new for d in diffs} == {"a.txt": False, "new.txt": True}
    modified = next(d.diff for d in diffs if d.path == "a.txt")
    assert modified.startswith("--- a/a.txt\n+++ b/a.txt\n@@")
    assert "-zero" in modified
    assert "+changed" in modified
    assert "diff --git" not in modified


async def test_commit_diffs_survives_a_body_that_looks_like_a_header(repo: Git, workspace: Path) -> None:
    (workspace / "notes.md").write_text("diff --git a/fake b/fake\nnew file mode 100644\n")
    sha = await repo.commit_all("prose about git")
    assert sha

    assert [d.path for d in await repo.commit_diffs(sha, max_chars=10_000)] == ["notes.md"]


async def test_commit_diffs_skips_a_patch_over_the_cap(repo: Git, workspace: Path) -> None:
    (workspace / "a.txt").write_text("x" * 500)
    sha = await repo.commit_all("bulky")
    assert sha

    assert await repo.commit_diffs(sha, max_chars=100) == []


async def test_checkout_detaches_at_the_requested_version(version_chain: VersionChain) -> None:
    await version_chain.git.checkout(version_chain.shas[0])

    assert version_chain.git.is_detached()
    assert await version_chain.git.head_sha() == version_chain.shas[0]
    assert (version_chain.workspace / "a.txt").read_text() == "zero"


async def test_restore_main_atomically_recreates_the_branch(version_chain: VersionChain) -> None:
    git = version_chain.git
    target = version_chain.shas[1]
    await git.checkout(target)
    await git._run("branch", "-D", "main")

    await git.restore_main(target)

    assert not git.is_detached()
    assert await git.head_sha() == target
    assert await git._run("rev-parse", "main") == target
    assert (version_chain.workspace / "a.txt").read_text() == "one"


def test_runs_on_a_selector_event_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "WORKSPACE_BASE_DIR", str(tmp_path))
    (tmp_path / "selector-loop").mkdir()
    git = Git("selector-loop")

    loop = asyncio.SelectorEventLoop()
    try:
        assert loop.run_until_complete(git.init("v0")) is None
    finally:
        loop.close()
