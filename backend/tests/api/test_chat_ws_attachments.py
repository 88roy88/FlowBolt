from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from flow44.ai.state import BuildState
from flow44.db.uploads import Upload, UploadKind
from flow44.main import app

from .test_chat_ws_selected_elements import PROJECT_ID, _send_message

client = TestClient(app, raise_server_exceptions=False)

SHOT = Upload(
    project_id=PROJECT_ID,
    kind=UploadKind.attachment,
    name="shot.png",
    s3_key="k",
    content_type="image/png",
    size_bytes=4,
    width=800,
    height=600,
    created_by="user-a",
)


def test_attachments_are_saved_with_the_message_and_shown_in_the_event() -> None:
    with (
        patch("flow44.api.chat.get_uploads", AsyncMock(return_value=[SHOT])),
        patch("flow44.ai.attachments.supports_vision", return_value=True),
    ):
        result = _send_message({"type": "message", "content": "match this", "attachmentIds": [SHOT.id]})

    assert result["saved_kwargs"]["attachment_ids"] == [SHOT.id]
    assert result["event"]["attachments"] == [
        {"id": SHOT.id, "name": "shot.png", "content_type": "image/png", "width": 800, "height": 600}
    ]


def _refused(payload: dict[str, Any], uploads: list[Upload], *, vision: bool = True) -> dict[str, Any]:
    project = MagicMock()
    project.id = PROJECT_ID
    project.user_id = "user-a"
    start_turn = AsyncMock()
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_user_id", new_callable=AsyncMock, return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mgr,
        patch("flow44.api.chat.versioning.broadcast_current_version", new_callable=AsyncMock),
        patch("flow44.api.chat.get_uploads", AsyncMock(return_value=uploads)),
        patch("flow44.ai.attachments.supports_vision", return_value=vision),
        patch("flow44.api.chat._start_turn", start_turn),
    ):
        mgr.wake_sandbox = AsyncMock(return_value=MagicMock())
        with client.websocket_connect(f"/ws/chat/{PROJECT_ID}", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json(payload)
            reply = ws.receive_json()
    start_turn.assert_not_awaited()
    return reply


def test_an_image_for_a_model_without_vision_is_refused() -> None:
    reply = _refused({"type": "message", "content": "hi", "attachmentIds": [SHOT.id]}, [SHOT], vision=False)

    assert reply["type"] == "error"
    assert "can't read images" in reply["message"]


def test_an_unknown_attachment_is_refused() -> None:
    reply = _refused({"type": "message", "content": "hi", "attachmentIds": [SHOT.id, "other-project"]}, [SHOT])

    assert reply["type"] == "error"
    assert "couldn't be found" in reply["message"]


def test_accepting_a_plan_with_a_model_without_vision_is_refused() -> None:
    state = BuildState(project_id=PROJECT_ID, attachment_ids=[SHOT.id])
    payload = {"type": "plan_response", "action": "accept", "model": "text-only"}

    with patch("flow44.api.chat.get_pending_plan", AsyncMock(return_value=state.model_dump_json())):
        reply = _refused(payload, [SHOT], vision=False)

    assert reply["type"] == "error"
    assert "can't read images" in reply["message"]
