"""Tests for ExecuteAgent._execute_task contract enforcement."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from flow44.ai.agents.execute import agent as execute_agent
from flow44.ai.agents.execute.agent import ExecuteAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.agents.execute.models import Task, WorkPlan
from flow44.ai.agents.plan.models import ArchitectureDesign, UXDesign
from flow44.ai.state import BuildState

_ARTIFACT = """<flowArtifact id="a" title="t">
<flowAction type="file" filePath="src/components/Foo.tsx">
FOO
</flowAction>
<flowAction type="file" filePath="src/components/Bar.tsx">
BAR
</flowAction>
</flowArtifact>"""


class _RecordingSandbox:
    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def write_file(self, path: str, content: str) -> None:
        self.written.append((path, content))


class _FakeSpan:
    id = "obs-1"

    def end(self) -> None:
        return None


class _FakeLangfuse:
    def span(self, **_kwargs: Any) -> _FakeSpan:
        return _FakeSpan()


async def _noop_emit(_event: dict[str, Any]) -> None:
    return None


async def test_execute_task_drops_unexpected_file_but_writes_expected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        yield _ARTIFACT

    monkeypatch.setattr(execute_agent, "stream_chat", _fake_stream)

    sandbox = _RecordingSandbox()
    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    build_state = BuildState(project_id="p")
    build_state.work_plan = WorkPlan(
        id="w",
        summary="",
        architecture=ArchitectureDesign(),
        ux_design=UXDesign(),
        tasks=[task],
    )
    state = ExecutionState(
        build_state=build_state,
        project_id="p",
        sandbox_ref=sandbox,
        emit_fn=_noop_emit,
        langfuse_client=_FakeLangfuse(),
        llm_metadata_fn=lambda _name: {},
    )

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._execute_task(task, state)

    assert sandbox.written == [("src/components/Foo.tsx", "FOO")]
    assert build_state.completed_files == {"src/components/Foo.tsx": "FOO"}
    assert task.status == "completed"
