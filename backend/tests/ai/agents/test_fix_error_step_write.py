"""Tests for FixErrorAgent._step_write, _step_retry, routing, and completion."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from flow44.ai.agents.fix_error import agent as fix_error_agent
from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.fix_error.fix_error_state import FixErrorState
from flow44.ai.file_safety import FileSafetyError


class _RecordingSandbox:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files = dict(files or {})
        self.written: list[tuple[str, str]] = []

    async def read_file(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def write_file(self, path: str, content: str) -> None:
        self.files[path] = content
        self.written.append((path, content))


async def _noop_emit(_event: dict[str, Any]) -> None:
    return None


def _make_state(sandbox: _RecordingSandbox) -> FixErrorState:
    return FixErrorState(
        project_id="p",
        sandbox_ref=sandbox,
        emit_fn=_noop_emit,
        error_message="boom",
        llm_metadata_fn=lambda _name: {},
    )


def _make_agent(sandbox: _RecordingSandbox | None = None) -> FixErrorAgent:
    agent = FixErrorAgent.__new__(FixErrorAgent)
    agent.sandbox = sandbox  # type: ignore[assignment]
    agent.emit = _noop_emit  # type: ignore[method-assign]
    agent.project_id = "p"
    return agent


def _silence_save_message(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_save(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr("flow44.ai.agents._chat_agent.save_message", _fake_save)


async def test_step_write_drops_protected_file_and_records_rejection() -> None:
    sandbox = _RecordingSandbox()
    state = FixErrorState(
        project_id="p",
        sandbox_ref=sandbox,
        emit_fn=_noop_emit,
        error_message="boom",
        new_files=[("src/main.tsx", "x"), ("src/components/Foo.tsx", "y")],
    )

    agent = _make_agent(sandbox)
    result = await agent._step_write(state)

    assert sandbox.written == [("src/components/Foo.tsx", "y")]
    assert result.changed_files == {"src/components/Foo.tsx": "y"}
    assert len(result.rejected_files) == 1


async def test_step_write_applies_edits_to_existing_file() -> None:
    sandbox = _RecordingSandbox({"src/App.tsx": "const a = 1;\nconst b = 2;\n"})
    state = _make_state(sandbox)
    state.edits = [("src/App.tsx", [("const b = 2;", "const b = 3;")])]

    result = await _make_agent(sandbox)._step_write(state)

    assert sandbox.files["src/App.tsx"] == "const a = 1;\nconst b = 3;\n"
    assert result.changed_files == {"src/App.tsx": "const a = 1;\nconst b = 3;\n"}
    assert result.edit_failures == []


async def test_step_write_refuses_full_rewrite_of_existing_file() -> None:
    sandbox = _RecordingSandbox({"src/App.tsx": "original"})
    state = _make_state(sandbox)
    state.new_files = [("src/App.tsx", "rewritten")]

    result = await _make_agent(sandbox)._step_write(state)

    assert sandbox.files["src/App.tsx"] == "original"
    assert sandbox.written == []
    assert len(result.edit_failures) == 1
    assert "already exists" in result.edit_failures[0]


async def test_step_write_applies_no_edits_to_file_when_one_fails() -> None:
    sandbox = _RecordingSandbox({"src/App.tsx": "const a = 1;\nconst b = 2;\n"})
    state = _make_state(sandbox)
    state.edits = [("src/App.tsx", [("const a = 1;", "const a = 9;"), ("const missing", "x")])]

    result = await _make_agent(sandbox)._step_write(state)

    assert sandbox.written == []
    assert result.changed_files == {}
    assert len(result.edit_failures) == 1
    assert "search block 2 was not found" in result.edit_failures[0]


async def test_step_write_rejects_edit_to_protected_file() -> None:
    sandbox = _RecordingSandbox({"src/main.tsx": "x"})
    state = _make_state(sandbox)
    state.edits = [("src/main.tsx", [("x", "y")])]

    result = await _make_agent(sandbox)._step_write(state)

    assert sandbox.written == []
    assert len(result.rejected_files) == 1


def test_route_after_validate_retries_on_edit_failures() -> None:
    state = _make_state(_RecordingSandbox())
    state.edit_failures = ["No edits to src/App.tsx were applied"]

    assert FixErrorAgent.__new__(FixErrorAgent)._route_after_validate(state) == "retry"


def test_route_after_validate_treats_rejections_like_errors() -> None:
    state = _make_state(_RecordingSandbox())
    agent = FixErrorAgent.__new__(FixErrorAgent)

    assert agent._route_after_validate(state) == "complete"

    state.rejected_files = [FileSafetyError("something rejected")]
    assert agent._route_after_validate(state) == "retry"

    state.retry_count = fix_error_agent.MAX_RETRY_ATTEMPTS
    assert agent._route_after_validate(state) == "complete"


async def test_step_complete_emits_notice_for_unresolved_rejections(monkeypatch: pytest.MonkeyPatch) -> None:
    _silence_save_message(monkeypatch)
    events: list[dict[str, Any]] = []

    async def _recording_emit(event: dict[str, Any]) -> None:
        events.append(event)

    state = _make_state(_RecordingSandbox())
    state.emit_fn = _recording_emit
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = _make_agent()
    await agent._step_complete(state)

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "rejected" in error_events[0]["message"]


async def test_step_complete_emits_no_notice_when_nothing_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _silence_save_message(monkeypatch)
    events: list[dict[str, Any]] = []

    async def _recording_emit(event: dict[str, Any]) -> None:
        events.append(event)

    state = _make_state(_RecordingSandbox())
    state.emit_fn = _recording_emit

    agent = _make_agent()
    await agent._step_complete(state)

    assert [e for e in events if e["type"] == "error"] == []


async def test_step_retry_retains_rejections_when_stream_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raising_stream(*_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        async def _boom() -> AsyncIterator[str]:
            raise RuntimeError("stream exploded")
            yield

        return _boom()

    monkeypatch.setattr(fix_error_agent, "stream_chat", _raising_stream)

    state = _make_state(_RecordingSandbox())
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = FixErrorAgent.__new__(FixErrorAgent)
    await agent._step_retry(state)

    assert len(state.rejected_files) == 1
    assert "rejected" in str(state.rejected_files[0])


async def test_step_retry_composes_single_message(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[Any]] = []

    def _capturing_stream(messages: list[Any], *_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        captured.append(messages)

        async def _empty() -> AsyncIterator[str]:
            return
            yield

        return _empty()

    monkeypatch.setattr(fix_error_agent, "stream_chat", _capturing_stream)

    state = _make_state(_RecordingSandbox())
    state.validation_errors = "## TypeScript Errors\nboom"
    state.rejected_files = [FileSafetyError("something rejected")]

    agent = FixErrorAgent.__new__(FixErrorAgent)
    await agent._step_retry(state)

    assert len(captured) == 1
    assert len(captured[0]) == 1
    message = captured[0][0].content
    assert "boom" in message
    assert "Changes that could not be applied" in message
    assert "rejected" in message
    assert len(state.rejected_files) == 1
    assert "something rejected" in str(state.rejected_files[0])


async def test_step_retry_reports_edit_failures_and_shows_discovered_files(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[tuple[list[Any], str]] = []

    def _capturing_stream(messages: list[Any], prompt: str, *_args: Any, **_kwargs: Any) -> AsyncIterator[str]:
        captured.append((messages, prompt))

        async def _empty() -> AsyncIterator[str]:
            return
            yield

        return _empty()

    monkeypatch.setattr(fix_error_agent, "stream_chat", _capturing_stream)

    state = _make_state(_RecordingSandbox())
    state.discovered_files = {"src/App.tsx": "const discoveredMarker = 1;"}
    state.edit_failures = ["No edits to src/App.tsx were applied: search block 1 was not found."]

    await FixErrorAgent.__new__(FixErrorAgent)._step_retry(state)

    messages, prompt = captured[0]
    assert "Edits that could not be applied" in messages[0].content
    assert "search block 1 was not found" in messages[0].content
    assert "discoveredMarker" in prompt
