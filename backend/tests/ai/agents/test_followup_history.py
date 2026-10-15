from __future__ import annotations

import json
from typing import Any

import pytest

from flow44.ai.agents.followup import agent as followup_agent
from flow44.ai.agents.followup.agent import FollowUpAgent
from flow44.db.chat import ChatMessage, ChatRole


def _row(role: ChatRole, content: str = "", raw: dict[str, Any] | None = None) -> ChatMessage:
    return ChatMessage(project_id="p", role=role, content=content, raw_message=raw)


def _run(n: int) -> list[ChatMessage]:
    call = {"id": f"call-{n}", "type": "function", "function": {"name": "grep", "arguments": "{}"}}
    return [
        _row(ChatRole.user, f"request {n}"),
        _row(ChatRole.assistant, raw={"role": "assistant", "content": "x" * 100, "tool_calls": [call]}),
        _row(ChatRole.tool, raw={"role": "tool", "tool_call_id": f"call-{n}", "content": "y" * 100}),
        _row(ChatRole.assistant, raw={"role": "assistant", "content": f"done {n}"}),
    ]


def _history(runs: int) -> list[ChatMessage]:
    return [row for n in range(runs) for row in _run(n)]


def _convert(history: list[ChatMessage]) -> list[Any]:
    return object.__new__(FollowUpAgent)._history_to_messages(history)


def _role(message: Any) -> str:
    return message["role"] if isinstance(message, dict) else message.role


def _user_requests(messages: list[Any]) -> list[str]:
    return [m.content for m in messages if not isinstance(m, dict)]


def test_history_under_budget_is_kept_whole() -> None:
    assert len(_convert(_history(30))) == 120


def test_history_over_budget_is_cut_at_a_run_start_and_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(followup_agent, "HISTORY_CHAR_BUDGET", 3000)
    history = _history(30)
    messages = _convert(history)

    assert _role(messages[0]) == "user"
    assert 20 < len(messages) < 120
    kept = history[-len(messages) :]
    assert sum(len(json.dumps(m.raw_message)) if m.raw_message else len(m.content) for m in kept) <= 3000
    seen_call_ids: set[str] = set()
    for m in messages:
        if _role(m) == "assistant":
            seen_call_ids |= {tc["id"] for tc in m.get("tool_calls", [])}
        if _role(m) == "tool":
            assert m["tool_call_id"] in seen_call_ids


def test_last_runs_are_kept_even_when_they_exceed_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(followup_agent, "HISTORY_CHAR_BUDGET", 10)
    messages = _convert(_history(30))

    assert _user_requests(messages) == [f"request {n}" for n in range(25, 30)]
    assert len(messages) == 20


def test_leaked_tool_call_text_is_skipped() -> None:
    history = [
        _row(ChatRole.user, "hi"),
        _row(ChatRole.assistant, '<invoke name="read_file"><parameter name="path">a</parameter></invoke>'),
        _row(ChatRole.assistant, "｜DSML｜ tool_calls"),
        _row(ChatRole.assistant, "all good"),
    ]

    assert [m.content for m in _convert(history)] == ["hi", "all good"]


def test_prose_mentioning_markup_names_is_kept() -> None:
    history = [_row(ChatRole.user, "hi"), _row(ChatRole.assistant, "DSML uses an <invoke> tag for tool calls.")]

    assert [m.content for m in _convert(history)] == ["hi", "DSML uses an <invoke> tag for tool calls."]


def test_rows_without_content_leave_no_placeholder() -> None:
    history = [_row(ChatRole.user, "hi"), _row(ChatRole.assistant, "  "), _row(ChatRole.user, "again")]

    assert [m.content for m in _convert(history)] == ["hi", "again"]
