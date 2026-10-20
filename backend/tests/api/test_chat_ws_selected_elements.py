from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)

PROJECT_ID = "proj-elements"
ELEMENT = {"tag": "button", "selector": "main > button.cta", "text": "Sign up", "components": ["App"]}


def _send_message(payload: dict[str, Any]) -> dict[str, Any]:
    project = MagicMock()
    project.id = PROJECT_ID
    project.user_id = "user-a"
    save_message = AsyncMock()
    emit_event = AsyncMock()
    done = threading.Event()
    captured: dict[str, Any] = {}

    async def fake_start_turn(
        project_id: str, make_coro: Callable[[], Any], prepare: Callable[[], Awaitable[Any]] | None = None
    ) -> None:
        if prepare is not None:
            await prepare()
        captured["run_args"] = make_coro.args  # type: ignore[attr-defined]
        done.set()

    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_user_id", new_callable=AsyncMock, return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mgr,
        patch("flow44.api.chat.versioning.broadcast_current_version", new_callable=AsyncMock),
        patch("flow44.api.chat._is_new_project", new_callable=AsyncMock, return_value=False),
        patch("flow44.api.chat.FollowUpAgent"),
        patch("flow44.api.chat._start_turn", fake_start_turn),
        patch("flow44.api.chat.save_message", save_message),
        patch("flow44.api.chat.emit_event", emit_event),
        patch("flow44.api.chat.count_user_messages", new_callable=AsyncMock, return_value=1),
        patch("flow44.api.chat.log_bi_event") as log_bi_event,
    ):
        mgr.wake_sandbox = AsyncMock(return_value=MagicMock())
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json(payload)
            assert done.wait(timeout=5), "turn was not started"

    assert save_message.await_args is not None
    assert emit_event.await_args is not None
    captured["saved_content"] = save_message.await_args.args[2]
    captured["event"] = emit_event.await_args.args[1]
    captured["prompt_length"] = log_bi_event.call_args.kwargs["prompt_length"]
    return captured


def test_selected_elements_reach_the_model_and_the_event() -> None:
    result = _send_message({"type": "message", "content": "make this red", "selectedElements": [ELEMENT]})

    model_content = result["run_args"][0]
    assert model_content.startswith("make this red\n\n<selected_elements>")
    assert "main > button.cta" in model_content
    assert result["saved_content"] == model_content
    assert result["event"]["content"] == "make this red"
    assert result["event"]["selected_elements"][0]["tag"] == "button"
    assert result["prompt_length"] == len("make this red")


def test_message_without_elements_is_unchanged() -> None:
    result = _send_message({"type": "message", "content": "make it red"})

    assert result["run_args"][0] == "make it red"
    assert result["saved_content"] == "make it red"
    assert "selected_elements" not in result["event"]
