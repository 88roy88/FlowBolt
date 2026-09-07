from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from flow44.api import chat

PROJECT_ID = "test-project-run-agent-safe"
CLAIMED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _patch_boundary(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    emit = AsyncMock()
    clear = AsyncMock()
    commit = AsyncMock(return_value=None)
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 5)
    monkeypatch.setattr(chat, "emit_event", emit)
    monkeypatch.setattr(chat, "clear_heartbeat", clear)
    monkeypatch.setattr(chat.versioning, "commit_turn", commit)
    return emit, clear, commit


def _patch_heartbeat(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    touch = AsyncMock(return_value=datetime.now(UTC))
    monkeypatch.setattr(chat, "touch_heartbeat", touch)
    return touch


async def test_success_commits_and_emits_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    emit, clear, commit = _patch_boundary(monkeypatch)

    async def succeed() -> None:
        return None

    await chat._run_agent_safe(PROJECT_ID, succeed(), CLAIMED_AT)

    emit.assert_not_awaited()
    clear.assert_awaited_once_with(PROJECT_ID, only_beat=CLAIMED_AT)
    commit.assert_awaited_once_with(PROJECT_ID)


async def test_failure_emits_error_without_committing(monkeypatch: pytest.MonkeyPatch) -> None:
    emit, clear, commit = _patch_boundary(monkeypatch)

    async def fail() -> None:
        raise RuntimeError("agent blew up")

    await chat._run_agent_safe(PROJECT_ID, fail(), CLAIMED_AT)

    emitted = [call.args[1] for call in emit.await_args_list]
    assert {"type": "phase", "phase": "idle"} in emitted
    assert {"type": "error", "message": "AI processing failed"} in emitted
    clear.assert_awaited_once_with(PROJECT_ID, only_beat=CLAIMED_AT)
    commit.assert_not_awaited()


async def test_supervisor_timeout_cancels_and_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    emit, clear, commit = _patch_boundary(monkeypatch)
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 0.05)
    monkeypatch.setattr(chat.settings, "AGENT_RUN_STALE_TIMEOUT", 0.8)
    cancelled = asyncio.Event()

    async def hang() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    await chat._run_agent_safe(PROJECT_ID, hang(), CLAIMED_AT)

    emitted = [call.args[1] for call in emit.await_args_list]
    assert {"type": "phase", "phase": "idle"} in emitted
    assert {"type": "error", "message": "AI processing timed out"} in emitted
    assert cancelled.is_set()
    clear.assert_awaited_once_with(PROJECT_ID, only_beat=CLAIMED_AT)
    commit.assert_not_awaited()


async def test_supervisor_beats_while_running(monkeypatch: pytest.MonkeyPatch) -> None:
    _, clear, _ = _patch_boundary(monkeypatch)
    touch = _patch_heartbeat(monkeypatch)
    monkeypatch.setattr(chat.settings, "AGENT_RUN_STALE_TIMEOUT", 0.04)

    async def work() -> None:
        await asyncio.sleep(0.05)

    await chat._run_agent_safe(PROJECT_ID, work(), CLAIMED_AT)

    assert touch.await_count >= 2
    clear.assert_awaited_once_with(PROJECT_ID, only_beat=touch.return_value)


async def test_claim_run_rejects_when_run_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat.versioning, "begin_turn", AsyncMock(return_value=None))

    with pytest.raises(chat.AgentAlreadyRunning):
        await chat._claim_run(PROJECT_ID)


async def test_claim_run_returns_the_claim_stamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat.versioning, "begin_turn", AsyncMock(return_value=CLAIMED_AT))

    assert await chat._claim_run(PROJECT_ID) == CLAIMED_AT


async def test_start_agent_runs_under_the_supervisor(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_boundary(monkeypatch)
    started = asyncio.Event()

    async def agent() -> None:
        started.set()

    chat._start_agent(PROJECT_ID, agent(), CLAIMED_AT)
    assert len(chat._RUNNING) == 1
    task = next(iter(chat._RUNNING))

    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.wait_for(task, timeout=1)
    assert set() == chat._RUNNING
