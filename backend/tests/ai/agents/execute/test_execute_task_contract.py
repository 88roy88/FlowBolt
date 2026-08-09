"""Tests for ExecuteAgent._execute_task contract enforcement."""

from __future__ import annotations

import json
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


class _BuildResult:
    def __init__(self, errors: str) -> None:
        self.errors = errors


class _RecordingSandbox:
    def __init__(self, errors: str = "") -> None:
        self.written: list[tuple[str, str]] = []
        self._errors = errors

    async def write_file(self, path: str, content: str) -> None:
        self.written.append((path, content))

    async def run_build_command(self, _command: str) -> _BuildResult:
        return _BuildResult(self._errors)


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
        llm_metadata_fn=lambda _name, **_kwargs: {},
    )


def _stream_artifact(artifact: str) -> Any:
    async def _fake_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        yield artifact

    return _fake_stream


class _StubStream:
    """Yields the next artifact per call, repeating the last one, and records the messages sent."""

    def __init__(self, *artifacts: str) -> None:
        self._artifacts = artifacts
        self.calls: list[list[Any]] = []

    def __call__(self, messages: list[Any], *_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        artifact = self._artifacts[min(len(self.calls), len(self._artifacts) - 1)]
        self.calls.append(messages)

        async def _gen() -> AsyncIterator[str]:
            yield artifact

        return _gen()


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


async def test_execute_task_retry_narrows_contract_and_names_missing_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _StubStream(_ARTIFACT)
    monkeypatch.setattr(execute_agent, "stream_chat", stream)

    sandbox = _RecordingSandbox()
    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx", "src/components/Bar.tsx"])
    state = _make_state(task, sandbox)

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._execute_task(task, state, retry_files=["src/components/Bar.tsx"])

    assert sandbox.written == [("src/components/Bar.tsx", "BAR")]
    message = stream.calls[0][0].content
    assert "did not produce" in message
    assert "src/components/Bar.tsx" in message


async def test_execute_task_retry_accumulates_task_files(monkeypatch: pytest.MonkeyPatch) -> None:
    foo_only = """<flowArtifact id="a" title="t">
<flowAction type="file" filePath="src/components/Foo.tsx">
FOO
</flowAction>
</flowArtifact>"""
    bar_only = """<flowArtifact id="a" title="t">
<flowAction type="file" filePath="src/components/Bar.tsx">
BAR
</flowAction>
</flowArtifact>"""
    monkeypatch.setattr(execute_agent, "stream_chat", _StubStream(foo_only, bar_only))

    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx", "src/components/Bar.tsx"])
    state = _make_state(task, _RecordingSandbox())

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._execute_task(task, state)
    await agent._execute_task(task, state, retry_files=["src/components/Bar.tsx"])

    assert state.build_state.task_files["t1"] == ["src/components/Foo.tsx", "src/components/Bar.tsx"]
    assert agent._unfulfilled(state) == []


async def test_step_execute_tasks_skips_retry_when_contract_fulfilled(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _StubStream(_ARTIFACT)
    monkeypatch.setattr(execute_agent, "stream_chat", stream)

    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx", "src/components/Bar.tsx"])
    state = _make_state(task, _RecordingSandbox())

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_execute_tasks(state)

    assert len(stream.calls) == 1
    assert task.status == "completed"
    assert state.unfulfilled_files == {}


async def test_step_execute_tasks_retries_once_then_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _StubStream("""<flowArtifact id="a" title="t"></flowArtifact>""")
    monkeypatch.setattr(execute_agent, "stream_chat", stream)

    events: list[dict[str, Any]] = []

    async def _recording_emit(event: dict[str, Any]) -> None:
        events.append(event)

    task = Task(id="t1", title="A", description="build the nav", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    state.emit_fn = _recording_emit

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_execute_tasks(state)

    assert len(stream.calls) == 2
    assert "did not produce" in stream.calls[1][0].content
    assert task.status == "failed"
    assert state.unfulfilled_files == {"src/components/Foo.tsx": "A: build the nav"}
    assert {"type": "task_update", "taskId": "t1", "status": "failed"} in events


async def test_step_validate_names_missing_files_alongside_errors() -> None:
    task = Task(id="t1", title="A", description="build the nav", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox(errors="boom"))
    state.unfulfilled_files = {"src/components/Foo.tsx": "A: build the nav"}

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_validate(state)

    assert "Files a task failed to produce" in state.all_errors
    assert "src/components/Foo.tsx — A: build the nav" in state.all_errors


async def test_step_validate_omits_missing_files_without_errors_or_once_written() -> None:
    task = Task(id="t1", title="A", description="build the nav", files=["src/components/Foo.tsx"])
    agent = ExecuteAgent.__new__(ExecuteAgent)

    clean = _make_state(task, _RecordingSandbox())
    clean.unfulfilled_files = {"src/components/Foo.tsx": "A: build the nav"}
    await agent._step_validate(clean)
    assert clean.all_errors == ""

    written = _make_state(task, _RecordingSandbox(errors="boom"))
    written.unfulfilled_files = {"src/components/Foo.tsx": "A: build the nav"}
    written.build_state.completed_files = {"src/components/Foo.tsx": "FOO"}
    await agent._step_validate(written)
    assert "Files a task failed to produce" not in written.all_errors


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
    assert len(captured[0]) == 1
    message = captured[0][0].content
    assert "boom" in message
    assert "Changes that could not be applied" in message
    assert "rejected" in message
    assert len(state.rejected_files) == 1
    assert "something rejected" in str(state.rejected_files[0])


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
    message = captured[0][0].content
    assert "## Build errors" in message
    assert "boom" in message
    assert "Changes that could not be applied" not in message


def test_route_after_validate_ignores_rejections_on_a_green_build() -> None:
    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    agent = ExecuteAgent.__new__(ExecuteAgent)

    assert agent._route_after_validate(state) == "summarize"

    state.rejected_files = [FileSafetyError("something rejected")]
    assert agent._route_after_validate(state) == "summarize"

    state.all_errors = "## Build Errors\nboom"
    assert agent._route_after_validate(state) == "fix_errors"

    state.fix_attempts = 10
    assert agent._route_after_validate(state) == "summarize"


async def test_step_fix_errors_rejection_only_composes_single_message(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert len(captured[0]) == 1
    message = captured[0][0].content
    assert "## Build errors" not in message
    assert "Changes that could not be applied" in message
    assert "rejected" in message
    assert len(state.rejected_files) == 1
    assert "something rejected" in str(state.rejected_files[0])


async def test_step_fix_errors_retains_rejections_when_stream_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raising_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        async def _boom() -> AsyncIterator[str]:
            raise RuntimeError("stream exploded")
            yield

        return _boom()

    monkeypatch.setattr(execute_agent, "stream_chat", _raising_stream)

    task = Task(id="t1", title="A", description="", files=["src/components/Foo.tsx"])
    state = _make_state(task, _RecordingSandbox())
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_fix_errors(state)

    assert len(state.rejected_files) == 1
    assert "rejected" in str(state.rejected_files[0])


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


async def test_step_summarize_drops_files_not_actually_written(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_complete_chat(*_args: Any, **_kwargs: Any) -> str:
        return json.dumps(
            {
                "summary": "s",
                "tech_stack": ["React"],
                "features": ["f"],
                "file_overview": {"src/App.tsx": "written", "src/main.tsx": "phantom"},
            }
        )

    async def _noop_update(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(execute_agent, "complete_chat", _fake_complete_chat)
    monkeypatch.setattr(execute_agent, "update_project_summary", _noop_update)

    events: list[dict[str, Any]] = []

    async def _recording_emit(event: dict[str, Any]) -> None:
        events.append(event)

    task = Task(id="t1", title="A", description="", files=["src/App.tsx"])
    state = _make_state(task, _RecordingSandbox())
    state.emit_fn = _recording_emit
    state.build_state.completed_files = {"src/App.tsx": "x"}

    agent = ExecuteAgent.__new__(ExecuteAgent)
    await agent._step_summarize(state)

    summary_events = [e for e in events if e["type"] == "project_summary"]
    assert len(summary_events) == 1
    file_overview = summary_events[0]["summary"]["file_overview"]
    assert "src/App.tsx" in file_overview
    assert "src/main.tsx" not in file_overview
