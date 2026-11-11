from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.core import react_flow
from flow44.ai.core.react_flow import (
    MALFORMED_TOOL_CALL_CORRECTION,
    MAX_ITERATIONS_FALLBACK,
    MAX_ITERATIONS_WRAP_UP,
    ReActFlow,
)
from flow44.ai.core.tools import ToolExecutor

LEAK = '<invoke name="read_file"><parameter name="path">a</parameter></invoke>'


def _response(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))])


def _patch_llm(monkeypatch: pytest.MonkeyPatch, *contents: str) -> list[list[dict[str, Any]]]:
    replies = iter(contents)
    seen: list[list[dict[str, Any]]] = []

    async def fake(messages: list[dict[str, Any]], **_: Any) -> SimpleNamespace:
        seen.append(list(messages))
        return _response(next(replies))

    monkeypatch.setattr(react_flow, "complete_chat_with_tools", fake)
    return seen


async def _loop(max_iterations: int = 3) -> str:
    flow: ReActFlow[Any] = ReActFlow(max_iterations=max_iterations)
    return await flow.react_loop([{"role": "user", "content": "go"}], "sys", ToolExecutor([]))


async def test_leaked_tool_call_is_corrected_then_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_llm(monkeypatch, LEAK, "clean answer")

    assert await _loop() == "clean answer"
    assert seen[1][-2:] == [
        {"role": "assistant", "content": LEAK},
        {"role": "user", "content": MALFORMED_TOOL_CALL_CORRECTION},
    ]


async def test_persistent_leaks_end_with_step_limit_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm(monkeypatch, LEAK, LEAK, LEAK, LEAK)

    assert await _loop() == MAX_ITERATIONS_FALLBACK


def _tool_call_response() -> SimpleNamespace:
    call = {"id": "call-1", "type": "function", "function": {"name": "noop", "arguments": "{}"}}
    message = SimpleNamespace(
        content="",
        tool_calls=[SimpleNamespace(id="call-1", function=SimpleNamespace(name="noop", arguments="{}"))],
        model_dump=lambda: {"role": "assistant", "content": "", "tool_calls": [call]},
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _patch_tool_loop(monkeypatch: pytest.MonkeyPatch, wrap_up: str | Exception) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def fake(messages: list[dict[str, Any]], **kwargs: Any) -> SimpleNamespace:
        calls.append({"messages": list(messages), **kwargs})
        if kwargs.get("tool_choice") != "none":
            return _tool_call_response()
        if isinstance(wrap_up, Exception):
            raise wrap_up
        return _response(wrap_up)

    monkeypatch.setattr(react_flow, "complete_chat_with_tools", fake)
    return calls


async def test_max_iterations_ends_with_tool_less_wrap_up(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_tool_loop(monkeypatch, "Did A, B is left.")
    flow: ReActFlow[Any] = ReActFlow(max_iterations=2)

    answer = await flow.react_loop([{"role": "user", "content": "go"}], "sys", ToolExecutor([]))

    assert answer == "Did A, B is left."
    assert flow.hit_max_iterations
    assert [c.get("tool_choice") for c in calls] == [None, None, "none"]
    assert calls[-1]["messages"][-1] == {"role": "user", "content": MAX_ITERATIONS_WRAP_UP}


@pytest.mark.parametrize("wrap_up", ["", LEAK, RuntimeError("boom")])
async def test_max_iterations_falls_back_when_wrap_up_is_unusable(
    monkeypatch: pytest.MonkeyPatch, wrap_up: str | Exception
) -> None:
    _patch_tool_loop(monkeypatch, wrap_up)

    assert await _loop(max_iterations=1) == MAX_ITERATIONS_FALLBACK


async def test_finishing_in_time_does_not_flag_max_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm(monkeypatch, "done")
    flow: ReActFlow[Any] = ReActFlow(max_iterations=2)

    assert await flow.react_loop([{"role": "user", "content": "go"}], "sys", ToolExecutor([])) == "done"
    assert not flow.hit_max_iterations
