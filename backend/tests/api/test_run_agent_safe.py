"""Tests for the _run_agent_safe watchdog in flow44.api.chat."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from flow44.ai.agent_runtime import is_agent_active, reset_agent_runtime
from flow44.api import chat

PROJECT_ID = "test-project-run-agent-safe"


def setup_function() -> None:
    reset_agent_runtime()


def teardown_function() -> None:
    reset_agent_runtime()


async def test_watchdog_timeout_releases_counter_and_emits_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 0.05)
    emit = AsyncMock()
    monkeypatch.setattr(chat, "emit_event", emit)

    async def _hang() -> None:
        await asyncio.sleep(10)

    await chat._run_agent_safe(PROJECT_ID, _hang())

    # Counter released despite the hang → alive flips back to false.
    assert is_agent_active(PROJECT_ID) is False

    emitted = [call.args[1] for call in emit.await_args_list]
    assert {"type": "phase", "phase": "idle"} in emitted
    assert {"type": "error", "message": "AI processing timed out"} in emitted


async def test_success_releases_counter_without_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 5)
    emit = AsyncMock()
    monkeypatch.setattr(chat, "emit_event", emit)

    async def _ok() -> None:
        return None

    await chat._run_agent_safe(PROJECT_ID, _ok())

    assert is_agent_active(PROJECT_ID) is False
    emit.assert_not_awaited()


async def test_exception_releases_counter_and_emits_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chat.settings, "AGENT_RUN_TIMEOUT", 5)
    emit = AsyncMock()
    monkeypatch.setattr(chat, "emit_event", emit)

    async def _boom() -> None:
        raise RuntimeError("agent blew up")

    await chat._run_agent_safe(PROJECT_ID, _boom())

    assert is_agent_active(PROJECT_ID) is False
    emitted = [call.args[1] for call in emit.await_args_list]
    assert {"type": "phase", "phase": "idle"} in emitted
    assert {"type": "error", "message": "AI processing failed"} in emitted
