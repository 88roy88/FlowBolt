"""Tests for the admin published-apps listing."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from flow44.api.admin import require_admin
from flow44.db.project import Project
from flow44.main import app

client = TestClient(app)


def _published_project(project_id: str, handle: str, published_at: str) -> Project:
    return Project(
        id=project_id,
        user_id="owner-1",
        name=f"App {project_id}",
        published_url=handle,
        published_at=published_at,
    )


class TestListPublishedApps:
    @pytest.fixture(autouse=True)
    def _as_admin(self):
        """test-user is not in SYSTEM_ADMIN_IDS, so the admin gate must be overridden."""
        app.dependency_overrides[require_admin] = lambda: "test-user"
        yield
        app.dependency_overrides.pop(require_admin, None)

    async def test_maps_project_rows_to_response(self):
        projects = [
            _published_project("proj-1", "my-app", "2026-01-02T00:00:00+00:00"),
            _published_project("proj-2", "proj-2", "2026-01-01T00:00:00+00:00"),
        ]
        with patch("flow44.api.admin.list_published_projects", return_value=projects):
            response = client.get("/api/admin/published-apps")

        assert response.status_code == 200
        assert response.json() == [
            {
                "project_id": "proj-1",
                "name": "App proj-1",
                "owner_id": "owner-1",
                "project_url": "my-app",
                "public_path": "/shared/my-app",
                "published_at": "2026-01-02T00:00:00+00:00",
            },
            {
                "project_id": "proj-2",
                "name": "App proj-2",
                "owner_id": "owner-1",
                "project_url": "proj-2",
                "public_path": "/shared/proj-2",
                "published_at": "2026-01-01T00:00:00+00:00",
            },
        ]

    async def test_no_published_apps_returns_empty_list(self):
        with patch("flow44.api.admin.list_published_projects", return_value=[]):
            response = client.get("/api/admin/published-apps")

        assert response.status_code == 200
        assert response.json() == []


class TestListPublishedAppsAuth:
    async def test_non_admin_is_forbidden(self):
        """No require_admin override here: the signed-in test-user is not a system admin."""
        with patch("flow44.api.admin.list_published_projects", return_value=[]) as mock_list:
            response = client.get("/api/admin/published-apps")

        assert response.status_code == 403
        mock_list.assert_not_called()
