"""Tests for terminal WebSocket access by sandbox mode.

In local mode the terminal runs unsandboxed, so only admins may open it.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from flow44.config import settings
from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)


@contextmanager
def _terminal_env(mode: str, user_id: str, admin_ids: list[str]) -> Iterator[MagicMock]:
    project = MagicMock(id="proj-123", user_id=user_id)
    sandbox = MagicMock()
    sandbox.get_or_create_pty.return_value.get_scrollback.return_value = b"scrollback"
    sandbox.get_or_create_pty.return_value.read.return_value = b""
    with (
        patch.object(settings, "SANDBOX_MODE", mode),
        patch.object(settings, "SYSTEM_ADMIN_IDS", admin_ids),
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.deps.get_user_id", return_value=user_id),
        patch("flow44.api.deps.sandbox_manager") as mock_mgr,
    ):
        mock_mgr.get_sandbox = AsyncMock(return_value=sandbox)
        yield sandbox


def _connects() -> bool:
    try:
        with client.websocket_connect("/ws/terminal/proj-123", headers={"cookie": "flow44_token=t"}) as ws:
            return ws.receive_bytes() == b"scrollback"
    except WebSocketDisconnect:
        return False


def test_local_mode_rejects_non_admin() -> None:
    with _terminal_env("local", "user-a", admin_ids=[]) as sandbox:
        assert not _connects()
        sandbox.get_or_create_pty.assert_not_called()


@pytest.mark.parametrize(
    ("mode", "admin_ids"),
    [("local", ["user-a"]), ("namespaced", []), ("namespaced", ["user-a"])],
)
def test_terminal_allowed(mode: str, admin_ids: list[str]) -> None:
    with _terminal_env(mode, "user-a", admin_ids):
        assert _connects()
