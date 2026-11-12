"""Debug routes are admin-only: reaping a sandbox and listing a pod's live sandboxes."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.api.deps import require_admin
from flow44.main import app

client = TestClient(app)


class TestNonAdmin:
    """test-user is not in SYSTEM_ADMIN_IDS."""

    async def test_cannot_reap(self):
        with patch("flow44.api.projects.sandbox_manager.suspend_sandbox", AsyncMock()) as suspend:
            response = client.post("/api/projects/proj-1/debug/reap")
        assert response.status_code == 403
        suspend.assert_not_awaited()

    async def test_cannot_list_sandboxes(self):
        assert client.get("/api/admin/debug/sandboxes").status_code == 403


class TestAdmin:
    @pytest.fixture(autouse=True)
    def _as_admin(self):
        app.dependency_overrides[require_admin] = lambda: "test-user"
        yield
        app.dependency_overrides.pop(require_admin, None)

    async def test_reaps_active_sandbox(self):
        with (
            patch("flow44.api.projects.sandbox_manager.has_active_sandbox", return_value=True),
            patch("flow44.api.projects.sandbox_manager.suspend_sandbox", AsyncMock()) as suspend,
        ):
            response = client.post("/api/projects/proj-1/debug/reap")
        assert response.json() == {"status": "reaped", "project_id": "proj-1"}
        suspend.assert_awaited_once_with("proj-1")

    async def test_lists_sandboxes(self):
        with patch("flow44.api.admin.sandbox_manager.active_project_ids", return_value=["proj-1"]):
            response = client.get("/api/admin/debug/sandboxes")
        assert response.json() == {"count": 1, "project_ids": ["proj-1"]}
