"""Tests for the Opik tracing setup."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from litellm.integrations.opik.opik_payload_builder import payload_builders


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
