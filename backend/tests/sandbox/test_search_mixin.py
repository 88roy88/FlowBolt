import shutil

import pytest

from flow44.sandbox.base import SandboxInfo
from flow44.sandbox.filesystem_mixin import FileSystemMixin
from flow44.sandbox.search_mixin import SearchMixin
from flow44.sandbox.unix_local import UnixSandbox
from .conftest import DummySandbox

rg_available = pytest.mark.skipif(shutil.which("rg") is None, reason="ripgrep (rg) not installed")


class _ExecSandbox(SearchMixin, FileSystemMixin, UnixSandbox):
    """Grep/glob test sandbox: real exec() from UnixSandbox + file ops from mixins."""


@pytest.fixture
def exec_sandbox(tmp_path):  # type: ignore[type-arg]
    info = SandboxInfo(project_id="test", workspace_dir=str(tmp_path), port=0)
    return _ExecSandbox(info)


@pytest.mark.asyncio
class TestGlob:
    async def test_matches_pattern(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/App.tsx", "")
        await sandbox.write_file("src/index.ts", "")
        await sandbox.write_file("README.md", "")
        results = await sandbox.glob("**/*.tsx")
        assert any(r.endswith("App.tsx") for r in results)
        assert not any(r.endswith(".ts") and not r.endswith(".tsx") for r in results)

    async def test_skips_skip_dirs(self, sandbox: DummySandbox, tmp_path) -> None:  # type: ignore[type-arg]
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.js").write_text("")
        await sandbox.write_file("src/App.tsx", "")
        results = await sandbox.glob("**/*.js")
        assert not any("node_modules" in r for r in results)

    async def test_returns_slash_prefixed_paths(self, sandbox: DummySandbox) -> None:
        await sandbox.write_file("src/App.tsx", "")
        results = await sandbox.glob("**/*.tsx")
        assert all(r.startswith("/") for r in results)

    async def test_empty_result(self, sandbox: DummySandbox) -> None:
        results = await sandbox.glob("**/*.xyz")
        assert results == []


@pytest.mark.asyncio
class TestGrep:
    @rg_available
    async def test_finds_matches(self, exec_sandbox: _ExecSandbox) -> None:
        await exec_sandbox.write_file("src/App.tsx", "const x = useState()\nconst y = 1\n")
        matches = await exec_sandbox.grep("useState")
        assert len(matches) >= 1
        assert any("useState" in m.content for m in matches)

    @rg_available
    async def test_returns_grep_matches(self, exec_sandbox: _ExecSandbox) -> None:
        await exec_sandbox.write_file("src/App.tsx", "line one\nhello world\nline three\n")
        matches = await exec_sandbox.grep("hello")
        assert len(matches) == 1
        assert matches[0].file.endswith("App.tsx")
        assert matches[0].line == 2
        assert "hello world" in matches[0].content

    @rg_available
    async def test_max_results(self, exec_sandbox: _ExecSandbox) -> None:
        content = "\n".join(f"match_{i}" for i in range(20))
        await exec_sandbox.write_file("data.txt", content)
        matches = await exec_sandbox.grep("match_", max_results=5)
        assert len(matches) <= 5

    @rg_available
    async def test_all_results_when_no_limit(self, exec_sandbox: _ExecSandbox) -> None:
        content = "\n".join(f"match_{i}" for i in range(20))
        await exec_sandbox.write_file("data.txt", content)
        matches = await exec_sandbox.grep("match_", max_results=None)
        assert len(matches) == 20

    @rg_available
    async def test_file_pattern(self, exec_sandbox: _ExecSandbox) -> None:
        await exec_sandbox.write_file("src/App.tsx", "hello from tsx")
        await exec_sandbox.write_file("src/util.py", "hello from py")
        matches = await exec_sandbox.grep("hello", file_pattern="*.tsx")
        assert all(m.file.endswith(".tsx") for m in matches)
        assert not any(m.file.endswith(".py") for m in matches)

    @rg_available
    async def test_no_matches_returns_empty(self, exec_sandbox: _ExecSandbox) -> None:
        await exec_sandbox.write_file("src/App.tsx", "nothing here")
        matches = await exec_sandbox.grep("ZZZNOMATCH")
        assert matches == []

    async def test_traversal_blocked(self, sandbox: DummySandbox) -> None:
        with pytest.raises(PermissionError):
            await sandbox.grep("pattern", path="../../etc")
