"""Tests for the Opik tracing setup."""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from litellm.integrations.opik.opik_payload_builder import payload_builders

from flow44.ai.core import opik_utils
from flow44.config import OpikSettings
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
    assert trace_update["tags"] == ["plan-agent", "project:id-1", "user:user", "project_name:Sales"]


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

    assert trace_update["tags"] == ["plan-agent", "project:id-1", "user:user"]


def test_opik_environment_reaches_the_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPIK_ENVIRONMENT", "unset")

    OpikSettings(OPIK_API_KEY="key", OPIK_ENVIRONMENT="staging")

    assert os.environ["OPIK_ENVIRONMENT"] == "staging"
