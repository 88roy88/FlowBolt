import pytest

import flow44.sandbox.search_mixin as search_mixin_module
from flow44.sandbox.search_mixin import SearchToolError
from .conftest import DummySandbox

async def _yield_lines(lines: list[str]):
    for line in lines:
        yield line


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
    async def test_finds_matches(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        monkeypatch.setattr(
            sandbox,
            "exec",
            lambda command: _yield_lines(
                [
                    '{"type":"match","data":{"path":{"text":"src/App.tsx"},"lines":{"text":"const x = useState()\\n"},"line_number":1,"submatches":[{"match":{"text":"useState"},"start":10,"end":18}]}}'
                ]
            ),
        )
        matches = await sandbox.grep("useState")
        assert len(matches) >= 1
        assert any("useState" in m.content for m in matches)

    async def test_returns_grep_matches(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        monkeypatch.setattr(
            sandbox,
            "exec",
            lambda command: _yield_lines(
                [
                    '{"type":"match","data":{"path":{"text":"src/App.tsx"},"lines":{"text":"hello world\\n"},"line_number":2,"submatches":[{"match":{"text":"hello"},"start":0,"end":5}]}}'
                ]
            ),
        )
        matches = await sandbox.grep("hello")
        assert len(matches) == 1
        assert matches[0].file.endswith("App.tsx")
        assert matches[0].line == 2
        assert "hello world" in matches[0].content

    async def test_max_results_passes_expected_flag(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        seen: dict[str, str] = {}

        async def _fake_exec(command: str):
            seen["command"] = command
            yield '{"type":"summary","data":{"elapsed_total":{"human":"0.01s"}}}'

        monkeypatch.setattr(sandbox, "exec", _fake_exec)
        matches = await sandbox.grep("match_", max_results=5)
        assert matches == []
        assert "--max-count 5" in seen["command"]

    async def test_all_results_when_no_limit(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        monkeypatch.setattr(
            sandbox,
            "exec",
            lambda command: _yield_lines(
                [
                    '{"type":"match","data":{"path":{"text":"data.txt"},"lines":{"text":"match_0\\n"},"line_number":1,"submatches":[{"match":{"text":"match_"},"start":0,"end":6}]}}\n',
                    '{"type":"match","data":{"path":{"text":"data.txt"},"lines":{"text":"match_1\\n"},"line_number":2,"submatches":[{"match":{"text":"match_"},"start":0,"end":6}]}}\n',
                ]
            ),
        )
        matches = await sandbox.grep("match_", max_results=None)
        assert len(matches) == 2

    async def test_file_pattern_passes_expected_flag(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        seen: dict[str, str] = {}

        async def _fake_exec(command: str):
            seen["command"] = command
            yield '{"type":"summary","data":{"elapsed_total":{"human":"0.01s"}}}'

        monkeypatch.setattr(sandbox, "exec", _fake_exec)
        matches = await sandbox.grep("hello", file_pattern="*.tsx")
        assert matches == []
        assert "--glob" in seen["command"]
        assert "*.tsx" in seen["command"]

    async def test_no_matches_returns_empty(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        monkeypatch.setattr(
            sandbox,
            "exec",
            lambda command: _yield_lines(['{"type":"summary","data":{"elapsed_total":{"human":"0.01s"}}}']),
        )
        matches = await sandbox.grep("ZZZNOMATCH")
        assert matches == []

    async def test_raises_when_rg_missing(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: None)

        with pytest.raises(SearchToolError, match="ripgrep \\(rg\\) is required"):
            await sandbox.grep("pattern")

    async def test_raises_when_rg_returns_no_output(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        monkeypatch.setattr(sandbox, "exec", lambda command: _yield_lines([]))

        with pytest.raises(SearchToolError, match="Ripgrep returned no output"):
            await sandbox.grep("pattern")

    async def test_traversal_blocked(self, sandbox: DummySandbox, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(search_mixin_module.shutil, "which", lambda _name: "rg")
        with pytest.raises(PermissionError):
            await sandbox.grep("pattern", path="../../etc")
