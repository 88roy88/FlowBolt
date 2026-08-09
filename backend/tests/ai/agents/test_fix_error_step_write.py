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
    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def read_file(self, path: str) -> str:
        raise FileNotFoundError(path)

    async def write_file(self, path: str, content: str) -> None:
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
        generated_files=[("src/main.tsx", "x"), ("src/components/Foo.tsx", "y")],
    )

    agent = _make_agent(sandbox)
    result = await agent._step_write(state)

    assert sandbox.written == [("src/components/Foo.tsx", "y")]
    assert result.generated_files == [("src/components/Foo.tsx", "y")]
    assert len(result.rejected_files) == 1


def test_route_after_validate_ignores_rejections_on_a_green_build() -> None:
    state = _make_state(_RecordingSandbox())
    agent = FixErrorAgent.__new__(FixErrorAgent)

    assert agent._route_after_validate(state) == "complete"

    state.rejected_files = [FileSafetyError("something rejected")]
    assert agent._route_after_validate(state) == "complete"

    state.validation_errors = "boom"
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
