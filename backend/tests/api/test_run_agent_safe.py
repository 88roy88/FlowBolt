"""Tests for the _run_agent_safe supervisor + _start_agent run-lock in flow44.api.chat."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from flow44.api import chat

PROJECT_ID = "test-project-run-agent-safe"
CLAIMED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _patch_heartbeat(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    touch = AsyncMock(return_value=datetime.now(UTC))
    clear = AsyncMock()
    monkeypatch.setattr(chat, "touch_heartbeat", touch)
    monkeypatch.setattr(chat, "clear_heartbeat", clear)
    return touch, clear


async def test_supervisor_timeout_emits_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 0.05)
    monkeypatch.setattr(chat.settings, "AGENT_RUN_STALE_TIMEOUT", 0.8)  # beat = stale/4 = 0.2
    emit = AsyncMock()
    monkeypatch.setattr(chat, "emit_event", emit)
    _, clear = _patch_heartbeat(monkeypatch)

    async def _hang() -> None:
        await asyncio.sleep(10)

    await chat._run_agent_safe(PROJECT_ID, _hang(), CLAIMED_AT)

    emitted = [call.args[1] for call in emit.await_args_list]
    assert {"type": "phase", "phase": "idle"} in emitted
    assert {"type": "error", "message": "AI processing timed out"} in emitted
    clear.assert_awaited_once()


async def test_success_emits_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 5)
    emit = AsyncMock()
    monkeypatch.setattr(chat, "emit_event", emit)
    _, clear = _patch_heartbeat(monkeypatch)

    async def _ok() -> None:
        return None

    await chat._run_agent_safe(PROJECT_ID, _ok(), CLAIMED_AT)

    emit.assert_not_awaited()
    clear.assert_awaited_once()


async def test_exception_emits_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 5)
    emit = AsyncMock()
    monkeypatch.setattr(chat, "emit_event", emit)
    _, clear = _patch_heartbeat(monkeypatch)

    async def _boom() -> None:
        raise RuntimeError("agent blew up")

    await chat._run_agent_safe(PROJECT_ID, _boom(), CLAIMED_AT)

    emitted = [call.args[1] for call in emit.await_args_list]
    assert {"type": "phase", "phase": "idle"} in emitted
    assert {"type": "error", "message": "AI processing failed"} in emitted
    clear.assert_awaited_once()


async def test_supervisor_beats_while_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 5)
    monkeypatch.setattr(chat.settings, "AGENT_RUN_STALE_TIMEOUT", 0.04)  # beat = stale/4 = 0.01
    touch, clear = _patch_heartbeat(monkeypatch)

    async def _work() -> None:
        await asyncio.sleep(0.05)

    await chat._run_agent_safe(PROJECT_ID, _work(), CLAIMED_AT)

    assert touch.await_count >= 2
    clear.assert_awaited_once()


async def test_start_agent_rejects_when_run_active(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat, "try_claim_run", AsyncMock(return_value=None))
    ran = False

    async def _agent() -> None:
        nonlocal ran
        ran = True

    result = await chat._start_agent(PROJECT_ID, _agent())

    assert result is False
    assert ran is False  # the coro was closed, never scheduled


async def test_start_agent_starts_when_claim_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chat, "try_claim_run", AsyncMock(return_value=CLAIMED_AT))
    monkeypatch.setattr(chat, "emit_event", AsyncMock())
    _patch_heartbeat(monkeypatch)
    started = asyncio.Event()

    async def _agent() -> None:
        started.set()

    result = await chat._start_agent(PROJECT_ID, _agent())

    assert result is True
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.01)  # let the supervisor finish and clear the heartbeat
