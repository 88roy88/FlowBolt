from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.core import react_flow
from flow44.ai.core.react_flow import MALFORMED_TOOL_CALL_CORRECTION, ReActFlow
from flow44.ai.core.tools import ToolExecutor, ToolResult

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


def _capture_span_updates(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    monkeypatch.setattr(react_flow, "update_span", lambda **fields: updates.update(fields))
    return updates


def _tools_returning(result: ToolResult) -> Any:
    async def execute(tool_name: str, tool_use_id: str | None = None, **_: Any) -> ToolResult:
        return result

    return SimpleNamespace(execute=execute)


async def test_tool_span_stores_trimmed_input_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    updates = _capture_span_updates(monkeypatch)
    value = "x" * 5000

    result = await react_flow._execute_tool(_tools_returning(ToolResult(value)), "read_file", "id", {"content": value})

    assert result.value == value
    assert updates["name"] == "read_file"
    assert len(updates["input"]["content"]) < len(value)
    assert len(updates["output"]["result"]) == 2000
    assert "error_info" not in updates


async def test_tool_span_is_marked_as_failed_when_the_tool_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    updates = _capture_span_updates(monkeypatch)

    await react_flow._execute_tool(_tools_returning(ToolResult("nope", is_error=True)), "read_file", "id", {})

    assert updates["error_info"]["exception_type"] == "ToolError"
    assert updates["error_info"]["message"] == "nope"


async def test_llm_metadata_lists_tool_names_not_full_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm(monkeypatch, "done")
    schema = {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}
    tools: Any = SimpleNamespace(get_schemas=lambda: [schema])
    metadata: list[dict[str, Any]] = []

    def metadata_fn(_: str, extra_metadata: dict[str, Any]) -> dict[str, Any]:
        metadata.append(extra_metadata)
        return {}

    flow: ReActFlow[Any] = ReActFlow(max_iterations=1)
    await flow.react_loop([{"role": "user", "content": "go"}], "sys", tools, metadata_fn=metadata_fn)

    assert metadata == [{"available_tools": ["read_file"]}]
