"""Tests for the Opik tracing setup."""

from __future__ import annotations

import asyncio
import functools
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from litellm.integrations.opik.opik_payload_builder import payload_builders
from opik.rest_api.errors import NotFoundError

from flow44.ai.core import opik_utils
from flow44.services.logging import _project_name as _log_project_name


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


def _capture_trace_update(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    trace_update: dict[str, Any] = {}
    monkeypatch.setattr(opik_utils.opik_context, "get_current_trace_data", lambda: None)
    monkeypatch.setattr(opik_utils.opik_context, "update_current_trace", lambda **kwargs: trace_update.update(kwargs))
    return trace_update


def test_setup_trace_adds_the_project_name(monkeypatch: pytest.MonkeyPatch) -> None:
    trace_update = _capture_trace_update(monkeypatch)
    token = _log_project_name.set("Sales")

    try:
        opik_utils.setup_trace("id-1", "user", None, ["plan-agent"])
    finally:
        _log_project_name.reset(token)

    assert trace_update["thread_id"] == "id-1"
    assert trace_update["metadata"]["project_name"] == "Sales"
    assert trace_update["tags"] == ["plan-agent", "project:id-1", "project_name:Sales"]


def test_setup_trace_cuts_the_project_name_tag_to_the_opik_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    trace_update = _capture_trace_update(monkeypatch)
    token = _log_project_name.set("x" * 300)

    try:
        opik_utils.setup_trace("id-1", "user", None, [])
    finally:
        _log_project_name.reset(token)

    assert len(trace_update["tags"][-1]) == 100


def test_setup_trace_without_a_project_name_adds_no_name_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    trace_update = _capture_trace_update(monkeypatch)

    opik_utils.setup_trace("id-1", "user", None, ["plan-agent"])

    assert trace_update["tags"] == ["plan-agent", "project:id-1"]


async def test_tag_thread_tags_in_the_background(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    tagged = threading.Event()

    def _tag(thread_id: str, tags: list[str]) -> None:
        calls.append((thread_id, tags))
        tagged.set()

    monkeypatch.setattr(opik_utils, "_tag_thread", _tag)
    monkeypatch.setattr(opik_utils.settings, "OPIK_API_KEY", "key")
    token = _log_project_name.set("Sales")

    try:
        opik_utils.tag_thread("id-1")
    finally:
        _log_project_name.reset(token)

    assert tagged.wait(timeout=5)
    assert calls == [("id-1", ["project_name:Sales"])]


@pytest.mark.parametrize(("project_name", "api_key"), [(None, "key"), ("Sales", None)])
async def test_tag_thread_does_nothing_without_a_name_or_opik(
    monkeypatch: pytest.MonkeyPatch, project_name: str | None, api_key: str | None
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(opik_utils, "_tag_thread", lambda *args: calls.append(args))
    monkeypatch.setattr(opik_utils.settings, "OPIK_API_KEY", api_key)
    token = _log_project_name.set(project_name)

    try:
        opik_utils.tag_thread("id-1")
        await asyncio.sleep(0.05)
    finally:
        _log_project_name.reset(token)

    assert calls == []


def _fake_traces_client(monkeypatch: pytest.MonkeyPatch, get_trace_thread: Any, updates: list[Any]) -> None:
    traces = SimpleNamespace(
        get_trace_thread=get_trace_thread,
        update_thread=lambda model_id, tags: updates.append((model_id, tags)),
    )
    client = SimpleNamespace(rest_client=SimpleNamespace(traces=traces))
    monkeypatch.setattr(opik_utils, "get_global_client", lambda: client)
    monkeypatch.setattr(opik_utils, "_THREAD_WAIT_SECONDS", 0)


def test_tagging_waits_for_the_thread_to_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    updates: list[Any] = []
    lookups = iter([NotFoundError(body=None), NotFoundError(body=None), SimpleNamespace(thread_model_id="model-1")])

    def _get_trace_thread(**_: Any) -> Any:
        result = next(lookups)
        if isinstance(result, Exception):
            raise result
        return result

    _fake_traces_client(monkeypatch, _get_trace_thread, updates)

    opik_utils._tag_thread("id-1", ["project_name:Sales"])

    assert updates == [("model-1", ["project_name:Sales"])]


@pytest.mark.parametrize("error", [NotFoundError(body=None), RuntimeError("opik is down")])
def test_tagging_gives_up_without_raising(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    updates: list[Any] = []

    def _get_trace_thread(**_: Any) -> None:
        raise error

    _fake_traces_client(monkeypatch, _get_trace_thread, updates)

    opik_utils._tag_thread("id-1", ["project_name:Sales"])

    assert updates == []


def test_llm_spans_are_named_after_their_step() -> None:
    spans: list[dict[str, Any]] = []
    client = opik_utils._StepNamedSpanClient(SimpleNamespace(span=lambda **kwargs: spans.append(kwargs), flush=print))

    client.span(name="model_chat.completion_123", metadata={"generation_name": "followup-react-2"})
    client.span(name="model_failure", metadata=None)

    assert [span["name"] for span in spans] == ["followup-react-2", "model_failure"]
    assert client.flush is print
