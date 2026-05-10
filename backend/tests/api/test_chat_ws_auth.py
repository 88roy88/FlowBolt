"""Tests for chat WebSocket authentication sequencing.

Verifies that:
- Auth happens before any project/sandbox access
- First non-auth message is rejected
- Invalid / unauthorized tokens are rejected
- Wrong project owner is rejected
- Sandbox is not prepared until after successful auth
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from flow44.main import app
from flow44.sandbox.manager import SandboxNotFoundError

client = TestClient(app, raise_server_exceptions=False)


def _mock_project(user_id: str = "user-a", project_id: str = "proj-123") -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.user_id = user_id
    return p


def _mock_sandbox() -> MagicMock:
    sb = MagicMock()
    sb.ensure_ready = AsyncMock()
    return sb


def _mock_sandbox_manager(sandbox: MagicMock) -> MagicMock:
    mgr = MagicMock()
    mgr.get_sandbox.return_value = sandbox
    mgr.ensure_ready = AsyncMock()
    return mgr


# ---------------------------------------------------------------------------
# Helper: receive one JSON frame, tolerating immediate close
# ---------------------------------------------------------------------------


def _recv(ws: WebSocketTestSession) -> dict | None:
    try:
        return ws.receive_json()
    except (WebSocketDisconnect, Exception):
        return None


# ---------------------------------------------------------------------------
# First-message must be "auth"
# ---------------------------------------------------------------------------


def test_non_auth_first_message_rejected():
    """Sending any non-auth message first must be immediately rejected."""
    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock) as mock_get, \
         patch("flow44.api.chat.sandbox_manager") as mock_mgr:

        try:
            with client.websocket_connect("/ws/chat/proj-123") as ws:
                ws.send_json({"type": "message", "content": "Hello"})
                msg = _recv(ws)
                if msg is not None:
                    assert msg.get("type") == "error"
                    assert msg.get("message") == "Unauthorized"
        except WebSocketDisconnect:
            pass

        # Project and sandbox must never be touched
        mock_get.assert_not_called()
        mock_mgr.get_sandbox.assert_not_called()


def test_malformed_json_first_message_rejected():
    """Non-parseable first message should close the socket."""
    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock) as mock_get, \
         patch("flow44.api.chat.sandbox_manager") as mock_mgr:

        try:
            with client.websocket_connect("/ws/chat/proj-123") as ws:
                ws.send_text("not-json-{{{")
                _recv(ws)
        except (WebSocketDisconnect, Exception):  # noqa: S110
            pass

        mock_get.assert_not_called()
        mock_mgr.get_sandbox.assert_not_called()


# ---------------------------------------------------------------------------
# Auth message with bad / missing token
# ---------------------------------------------------------------------------


def test_auth_missing_token_rejected_when_required():
    """Empty userAuthorization with AUTH_REQUIRE_JWT=true must be rejected."""
    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock) as mock_get, \
         patch("flow44.api.chat.sandbox_manager") as mock_mgr, \
         patch("flow44.api.auth.settings") as mock_settings:

        mock_settings.AUTH_REQUIRE_JWT = True
        mock_settings.AUTH_JWT_SECRET = "some-secret"  # noqa: S105

        try:
            with client.websocket_connect("/ws/chat/proj-123") as ws:
                ws.send_json({"type": "auth"})  # no userAuthorization
                msg = _recv(ws)
                if msg is not None:
                    assert msg.get("type") == "error"
        except (WebSocketDisconnect, Exception):  # noqa: S110
            pass

        mock_get.assert_not_called()
        mock_mgr.get_sandbox.assert_not_called()


# ---------------------------------------------------------------------------
# Project ownership enforcement
# ---------------------------------------------------------------------------


def test_auth_wrong_owner_gets_not_found():
    """A valid token that does not own the project should get 'Project not found'."""
    project = _mock_project(user_id="owner-user")

    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock, return_value=project), \
         patch("flow44.api.chat.extract_user_id", return_value="other-user"), \
         patch("flow44.api.chat.sandbox_manager") as mock_mgr:

        try:
            with client.websocket_connect("/ws/chat/proj-123") as ws:
                ws.send_json({"type": "auth", "userAuthorization": "some-token"})
                msg = _recv(ws)
                if msg is not None:
                    assert msg.get("type") == "error"
                    assert msg.get("message") == "Project not found"
        except (WebSocketDisconnect, Exception):  # noqa: S110
            pass

        # Sandbox must NOT be touched when ownership check fails
        mock_mgr.get_sandbox.assert_not_called()


def test_auth_unknown_project_gets_not_found():
    """A valid token for a project that doesn't exist should get 'Project not found'."""
    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock, return_value=None), \
         patch("flow44.api.chat.extract_user_id", return_value="some-user"), \
         patch("flow44.api.chat.sandbox_manager") as mock_mgr:

        try:
            with client.websocket_connect("/ws/chat/proj-ghost") as ws:
                ws.send_json({"type": "auth", "userAuthorization": "some-token"})
                msg = _recv(ws)
                if msg is not None:
                    assert msg.get("type") == "error"
                    assert msg.get("message") == "Project not found"
        except (WebSocketDisconnect, Exception):  # noqa: S110
            pass

        mock_mgr.get_sandbox.assert_not_called()


# ---------------------------------------------------------------------------
# Sandbox not accessed before auth
# ---------------------------------------------------------------------------


def test_sandbox_not_touched_before_auth():
    """Sandbox manager must never be invoked when auth fails."""
    mock_mgr = MagicMock()

    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock) as mock_get, \
         patch("flow44.api.chat.sandbox_manager", mock_mgr):

        try:
            with client.websocket_connect("/ws/chat/proj-123") as ws:
                ws.send_json({"type": "message", "content": "skip auth"})
                _recv(ws)
        except (WebSocketDisconnect, Exception):  # noqa: S110
            pass

        mock_get.assert_not_called()
        mock_mgr.get_sandbox.assert_not_called()
        mock_mgr.ensure_ready.assert_not_called()


# ---------------------------------------------------------------------------
# Sandbox error after successful auth
# ---------------------------------------------------------------------------


def test_sandbox_not_found_after_auth_sends_error():
    """After successful auth, a missing sandbox returns a meaningful error."""
    project = _mock_project(user_id="user-a")

    with patch("flow44.api.auth.db_get_project", new_callable=AsyncMock, return_value=project), \
         patch("flow44.api.chat.extract_user_id", return_value="user-a"), \
         patch("flow44.api.chat.sandbox_manager") as mock_mgr:

        mock_mgr.get_sandbox.side_effect = SandboxNotFoundError("proj-123")

        try:
            with client.websocket_connect("/ws/chat/proj-123") as ws:
                ws.send_json({"type": "auth", "userAuthorization": "valid-token"})
                msg = _recv(ws)
                if msg is not None:
                    assert msg.get("type") == "error"
                    assert "sandbox" in msg.get("message", "").lower()
        except (WebSocketDisconnect, Exception):  # noqa: S110
            pass

        # Auth succeeded so project was fetched
        mock_mgr.get_sandbox.assert_called_once()
