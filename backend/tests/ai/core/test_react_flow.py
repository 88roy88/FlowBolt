from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.core import react_flow
from flow44.ai.core.react_flow import MALFORMED_TOOL_CALL_CORRECTION, ReActFlow
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


async def test_persistent_leaks_return_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm(monkeypatch, LEAK, LEAK, LEAK)

    assert await _loop() == ""
