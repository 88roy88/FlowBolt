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


def _make_state(task: Task, sandbox: _RecordingSandbox) -> ExecutionState:
    build_state = BuildState(project_id="p")
    build_state.work_plan = WorkPlan(
        id="w",
        summary="",
        architecture=ArchitectureDesign(),
        ux_design=UXDesign(),
        tasks=[task],
    )
    return ExecutionState(
        build_state=build_state,
        project_id="p",
        sandbox_ref=sandbox,
        emit_fn=_noop_emit,
        langfuse_client=_FakeLangfuse(),
        llm_metadata_fn=lambda _name: {},
    )


def _stream_artifact(artifact: str) -> Any:
    async def _fake_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        yield artifact

    return _fake_stream


async def test_execute_task_drops_unexpected_file_but_writes_expected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(execute_agent, "stream_chat", _stream_artifact(_ARTIFACT))

    sandbox = _RecordingSandbox()
    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, sandbox)

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._execute_task(task, state)

    assert sandbox.written == [("src/components/Foo.tsx", "FOO")]
    assert state.build_state.completed_files == {"src/components/Foo.tsx": "FOO"}
    assert task.status == "completed"
    assert state.rejected_file_notes == ["[task t1] File is outside the task contract: src/components/Bar.tsx"]


async def test_execute_task_records_note_for_unsafe_path(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = """<flowArtifact id="a" title="t">
<flowAction type="file" filePath="/etc/nowhere/Foo.tsx">
FOO
</flowAction>
</flowArtifact>"""
    monkeypatch.setattr(execute_agent, "stream_chat", _stream_artifact(artifact))

    sandbox = _RecordingSandbox()
    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, sandbox)

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._execute_task(task, state)

    assert sandbox.written == []
    assert task.status == "completed"
    assert len(state.rejected_file_notes) == 1
    assert "/etc/nowhere/Foo.tsx" in state.rejected_file_notes[0]


async def test_step_fix_errors_delivers_rejection_notes_as_message(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[Any]] = []

    def _capturing_stream(messages: list[Any], *_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        captured.append(messages)

        async def _empty() -> AsyncIterator[str]:
            return
            yield

        return _empty()

    monkeypatch.setattr(execute_agent, "stream_chat", _capturing_stream)

    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    state.all_errors = "## TypeScript Errors\nboom"
    state.rejected_file_notes = ["[task t1] something rejected"]

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_fix_errors(state)

    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert "rejected" in captured[0][1].content
    assert state.rejected_file_notes == []


async def test_step_fix_errors_sends_single_message_without_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[Any]] = []

    def _capturing_stream(messages: list[Any], *_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        captured.append(messages)

        async def _empty() -> AsyncIterator[str]:
            return
            yield

        return _empty()

    monkeypatch.setattr(execute_agent, "stream_chat", _capturing_stream)

    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    state.all_errors = "## TypeScript Errors\nboom"

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_fix_errors(state)

    assert len(captured) == 1
    assert len(captured[0]) == 1
