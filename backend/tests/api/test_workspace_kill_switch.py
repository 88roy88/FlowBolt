from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from flow44 import feature_flags
from flow44.api.admin import require_admin
from flow44.api.deps import require_platform_user
from flow44.main import app

SWITCH = "/api/admin/flags/disable_workspaces"
EXEMPT = "/api/admin/flags/disable_workspaces_exempt"


@pytest.fixture
def real_gate(monkeypatch):
    monkeypatch.setattr("flow44.workspace_gate.is_feature_enabled", feature_flags.is_feature_enabled)


@pytest.fixture
def as_admin():
    app.dependency_overrides[require_admin] = lambda: "test-user"
    app.dependency_overrides[require_platform_user] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(require_platform_user, None)


@pytest.mark.usefixtures("real_gate", "as_admin")
async def test_switch_blocks_workspaces_until_turned_off(async_client, test_db):
    assert (await async_client.get("/api/projects/some-project")).status_code == 404

    # Takes effect at once, despite the cached answer from the request above.
    await async_client.put(SWITCH, json={"enabled_for_all": True})

    for response in (
        await async_client.get("/api/projects/some-project"),
        await async_client.get("/api/files/some-project/tree"),
        await async_client.post("/api/projects", json={"name": "New"}),
    ):
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "workspaces_disabled"
    # What the blocked screen needs, and the way back, stay open.
    assert "disable_workspaces" in (await async_client.get("/api/config")).json()["features"]
    assert (await async_client.get("/api/projects")).status_code == 200

    await async_client.put(SWITCH, json={"enabled_for_all": False})

    assert (await async_client.get("/api/projects/some-project")).status_code == 404


@pytest.mark.usefixtures("real_gate", "as_admin")
async def test_switch_only_blocks_targeted_users(async_client, test_db):
    await async_client.post(f"{SWITCH}/targets", json={"target_type": "user", "target_id": "someone-else"})
    assert (await async_client.get("/api/projects/some-project")).status_code == 404

    await async_client.post(f"{SWITCH}/targets", json={"target_type": "user", "target_id": "test-user"})
    assert (await async_client.get("/api/projects/some-project")).status_code == 503


@pytest.mark.usefixtures("real_gate", "as_admin")
async def test_exempt_user_keeps_working_while_switched_on(async_client, test_db):
    await async_client.put(SWITCH, json={"enabled_for_all": True})
    await async_client.post(f"{EXEMPT}/targets", json={"target_type": "user", "target_id": "test-user"})

    assert (await async_client.get("/api/projects/some-project")).status_code == 404
    # The frontend works out the same answer from these two.
    features = (await async_client.get("/api/config")).json()["features"]
    assert {"disable_workspaces", "disable_workspaces_exempt"} <= set(features)

    await async_client.delete(f"{EXEMPT}/targets/user/test-user")

    assert (await async_client.get("/api/projects/some-project")).status_code == 503


def test_open_chat_socket_is_closed_once_switched_on():
    project = MagicMock(id="proj-gate", user_id="user-a")
    # Off for the handshake, on by the time the first message arrives.
    gate = AsyncMock(side_effect=[False, True])
    with (
        patch("flow44.api.deps.db_get_project", AsyncMock(return_value=project)),
        patch("flow44.api.deps.get_user_id", AsyncMock(return_value="user-a")),
        patch("flow44.workspace_gate.are_workspaces_disabled", gate),
        patch("flow44.api.chat.are_workspaces_disabled", gate),
        patch("flow44.api.chat.sandbox_manager.wake_sandbox", AsyncMock()),
        patch("flow44.api.chat.versioning.broadcast_current_version", AsyncMock()),
        patch("flow44.api.chat.versioning.begin_turn", AsyncMock()) as claim,
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws/chat/proj-gate", headers={"cookie": "flow44_token=t"}) as ws:
            ws.send_json({"type": "message", "content": "build me something"})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_json()

    assert closed.value.code == 1008
    claim.assert_not_awaited()
