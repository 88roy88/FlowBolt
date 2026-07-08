"""Tests for FixErrorAgent._step_write protected-file handling."""

from __future__ import annotations

from typing import Any

from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.fix_error.fix_error_state import FixErrorState


class _RecordingSandbox:
    def __init__(self) -> None:
        self.written: list[tuple[str, str]] = []

    async def write_file(self, path: str, content: str) -> None:
        self.written.append((path, content))


async def _noop_emit(_event: dict[str, Any]) -> None:
    return None


async def test_step_write_drops_protected_file_and_records_rejection() -> None:
    sandbox = _RecordingSandbox()
    state = FixErrorState(
        project_id="p",
        sandbox_ref=sandbox,
        emit_fn=_noop_emit,
        error_message="boom",
        generated_files=[("src/main.tsx", "x"), ("src/components/Foo.tsx", "y")],
    )

    agent = FixErrorAgent.__new__(FixErrorAgent)
    result = await agent._step_write(state)

    assert sandbox.written == [("src/components/Foo.tsx", "y")]
    assert result.generated_files == [("src/components/Foo.tsx", "y")]
    assert len(result.rejected_files) == 1
