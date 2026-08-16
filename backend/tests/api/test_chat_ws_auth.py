"""Tests for chat WebSocket cookie-based authentication.

Verifies that:
- Missing flow44_token cookie rejects the handshake before accept
- Wrong project owner rejects the handshake (sandbox never touched)
- Unknown project rejects the handshake (sandbox never touched)
- Valid cookie + missing sandbox connects then sends a JSON error frame
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)


def _mock_project(user_id: str = "user-a", project_id: str = "proj-123") -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.user_id = user_id
    return p


def _websocket_connect(path: str, token: str | None = None) -> WebSocketTestSession:
    headers = {"cookie": f"flow44_token={token}"} if token else {}
    return client.websocket_connect(path, headers=headers)


def _handshake_rejected(path: str, token: str | None) -> bool:
    """Return True if the handshake was rejected (no accept frame received)."""
    try:
        with _websocket_connect(path, token) as ws:
            try:
                ws.receive_json()
            except WebSocketDisconnect:
                return True
        return False
    except WebSocketDisconnect:
        return True


# ---------------------------------------------------------------------------
# Pre-accept auth rejection
# ---------------------------------------------------------------------------


def test_missing_cookie_rejected():
    """No cookie → handshake rejected before any backend logic runs."""
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock) as mock_get,
        patch("flow44.api.chat.sandbox_manager") as mock_mgr,
    ):
        assert _handshake_rejected("/ws/chat/proj-123", None)
        mock_get.assert_not_called()
        mock_mgr.get_sandbox.assert_not_called()


def test_wrong_owner_rejected():
    """Valid token whose user_id doesn't own the project → handshake rejected, sandbox untouched."""
    project = _mock_project(user_id="owner-user")
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_project_member", new_callable=AsyncMock, return_value=None),
        patch("flow44.api.deps.get_user_id", return_value="other-user"),
        patch("flow44.api.chat.sandbox_manager") as mock_mgr,
    ):
        assert _handshake_rejected("/ws/chat/proj-123", "any-token")
        mock_mgr.get_sandbox.assert_not_called()


def test_unknown_project_rejected():
    """Valid token for a non-existent project → handshake rejected, sandbox untouched."""
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=None),
        patch("flow44.api.deps.get_user_id", return_value="some-user"),
        patch("flow44.api.chat.sandbox_manager") as mock_mgr,
    ):
        assert _handshake_rejected("/ws/chat/proj-ghost", "any-token")
        mock_mgr.get_sandbox.assert_not_called()


def test_sandbox_not_touched_before_auth():
    """Failed auth must never invoke the sandbox manager."""
    mock_mgr = MagicMock()
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock) as mock_get,
        patch("flow44.api.chat.sandbox_manager", mock_mgr),
    ):
        assert _handshake_rejected("/ws/chat/proj-123", None)
        mock_get.assert_not_called()
        mock_mgr.get_sandbox.assert_not_called()
        mock_mgr.ensure_ready.assert_not_called()


# ---------------------------------------------------------------------------
# Post-accept errors (sandbox missing)
# ---------------------------------------------------------------------------


def test_sandbox_not_found_after_auth_sends_error():
    """After successful auth, a missing sandbox is surfaced as a JSON error frame."""
    project = _mock_project(user_id="user-a")
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_user_id", return_value="user-a"),
        patch("flow44.api.chat.sandbox_manager") as mock_mgr,
    ):
        mock_mgr.wake_sandbox = AsyncMock(side_effect=Exception("proj-123"))

        try:
            with _websocket_connect("/ws/chat/proj-123", "valid-token") as ws:
                msg = ws.receive_json()
                assert msg.get("type") == "error"
                assert "sandbox" in msg.get("message", "").lower()
        except WebSocketDisconnect:
            pass

        mock_mgr.wake_sandbox.assert_called_once()
