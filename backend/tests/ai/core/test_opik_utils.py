"""Tests for the Opik tracing setup."""

from __future__ import annotations

import asyncio
import functools
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from litellm.integrations.opik.opik_payload_builder import payload_builders

from flow44.ai.core import opik_utils


def test_litellm_span_ids_carry_the_current_time() -> None:
    now = datetime.now(UTC)
    span = payload_builders.build_span_payload(
        project_name="p",
        trace_id="t",
        parent_span_id=None,
        response_obj={},
        start_time=now,
        end_time=now,
        input_data={},
        output_data={},
        metadata={},
        tags=[],
        usage={},
        provider=None,
        cost=None,
    )

    id_timestamp_seconds = (uuid.UUID(span.id).int >> 80) / 1000
    assert abs(id_timestamp_seconds - time.time()) < 60


def _fake_opik_track(monkeypatch: pytest.MonkeyPatch) -> list[BaseException]:
    """Mimics opik.track: it only sees Exception, and closes the span when it does."""
    closed_with: list[BaseException] = []

    def _track(**_: Any) -> Callable[..., Any]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    closed_with.append(exc)
                    raise

            return wrapper

        return decorator

    monkeypatch.setattr(opik_utils.opik, "track", _track)
    return closed_with


async def test_track_closes_the_span_on_cancellation_and_stays_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    closed_with = _fake_opik_track(monkeypatch)
    started = asyncio.Event()

    @opik_utils.track(name="run")
    async def run() -> None:
        started.set()
        await asyncio.sleep(60)

    task = asyncio.create_task(run())
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
    assert len(closed_with) == 1


async def test_track_cancellation_skips_except_exception_in_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    closed_with = _fake_opik_track(monkeypatch)
    started = asyncio.Event()
    recovered = False

    @opik_utils.track(name="step")
    async def step() -> None:
        started.set()
        await asyncio.sleep(60)

    @opik_utils.track(name="run")
    async def run() -> None:
        nonlocal recovered
        try:
            await step()
        except Exception:
            recovered = True

    task = asyncio.create_task(run())
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert not recovered
    assert len(closed_with) == 2


async def test_track_passes_results_and_errors_through(monkeypatch: pytest.MonkeyPatch) -> None:
    closed_with = _fake_opik_track(monkeypatch)

    @opik_utils.track(name="ok")
    async def ok(value: int) -> int:
        return value + 1

    @opik_utils.track(name="fail")
    async def fail() -> None:
        raise ValueError("boom")

    assert await ok(1) == 2
    with pytest.raises(ValueError, match="boom"):
        await fail()
    assert [type(exc) for exc in closed_with] == [ValueError]
