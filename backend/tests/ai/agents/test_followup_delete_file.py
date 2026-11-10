from __future__ import annotations

from flow44.ai.agents.file_diffs import DiffTracker
from flow44.ai.agents.followup.agent import FollowUpAgent


class _FakeSandbox:
    def __init__(self, files: dict[str, str], dirs: set[str] | None = None) -> None:
        self.files = dict(files)
        self.dirs = dirs or set()
        self.deleted: list[str] = []

    async def read_file(self, path: str) -> str:
        if path in self.dirs:
            raise IsADirectoryError(path)
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def delete_file(self, path: str) -> None:
        del self.files[path]
        self.deleted.append(path)


def _make_agent(sandbox: _FakeSandbox) -> FollowUpAgent:
    agent = FollowUpAgent.__new__(FollowUpAgent)
    agent.sandbox = sandbox  # type: ignore[assignment]
    agent._diffs = DiffTracker()
    agent._executor = agent._build_tool_executor()
    return agent


async def _delete(agent: FollowUpAgent, path: str) -> str:
    return str((await agent._executor.execute("delete_file", path=path)).value)


async def test_delete_file_removes_file_and_records_full_removal_diff() -> None:
    sandbox = _FakeSandbox({"src/components/Old.tsx": "export const Old = 1;\n"})
    agent = _make_agent(sandbox)

    result = await _delete(agent, "src/components/Old.tsx")

    assert result == "OK — deleted src/components/Old.tsx"
    assert sandbox.deleted == ["src/components/Old.tsx"]
    [diff] = agent._diffs.combined_diffs()
    assert diff.path == "src/components/Old.tsx"
    assert diff.is_deleted is True
    assert "-export const Old = 1;" in diff.diff


async def test_delete_file_rejects_protected_file() -> None:
    sandbox = _FakeSandbox({"src/main.tsx": "x"})

    result = await _delete(_make_agent(sandbox), "src/main.tsx")

    assert result.startswith("Generated app contract violation: ")
    assert sandbox.deleted == []


async def test_delete_file_refuses_directories() -> None:
    sandbox = _FakeSandbox({}, dirs={"src/components"})

    result = await _delete(_make_agent(sandbox), "src/components")

    assert "not a deletable source file" in result
    assert sandbox.deleted == []
