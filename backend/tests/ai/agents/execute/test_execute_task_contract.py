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
from flow44.ai.file_safety import FileSafetyError
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
    assert len(state.rejected_files) == 1
    assert str(state.rejected_files[0]) == "File is outside the task contract: src/components/Bar.tsx"


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
    assert len(state.rejected_files) == 1
    assert "/etc/nowhere/Foo.tsx" in str(state.rejected_files[0])


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
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_fix_errors(state)

    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert "rejected" in captured[0][1].content
    assert state.rejected_files == []


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


def test_route_after_validate_treats_rejections_like_errors() -> None:
    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    agent = ExecuteAgent.__new__(ExecuteAgent)

    assert agent._route_after_validate(state) == "summarize"

    state.rejected_files = [FileSafetyError("something rejected")]
    assert agent._route_after_validate(state) == "fix_errors"

    state.fix_attempts = 10
    assert agent._route_after_validate(state) == "summarize"


async def test_step_fix_errors_rejection_only_uses_apply_changes_message(monkeypatch: pytest.MonkeyPatch) -> None:
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
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_fix_errors(state)

    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert captured[0][0].content == "Apply the required file changes."
    assert "rejected" in captured[0][1].content
    assert state.rejected_files == []


async def test_step_summarize_emits_error_for_unresolved_rejections(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_complete_chat(*_args: Any, **_kwargs: Any) -> str:
        return "{}"

    monkeypatch.setattr(execute_agent, "complete_chat", _fake_complete_chat)

    events: list[dict[str, Any]] = []

    async def _recording_emit(event: dict[str, Any]) -> None:
        events.append(event)

    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    state.emit_fn = _recording_emit
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_summarize(state)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "rejected" in error_events[0]["message"]
