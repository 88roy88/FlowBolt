"""Tests for the page-view beacon endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.auth.permissions import Role, get_owner_permissions, get_role_permissions
from flow44.db.page_view import PageViewSource
from flow44.db.project import Project
from flow44.main import app

client = TestClient(app)


def _project(published_at: str | None = "2026-01-01T00:00:00+00:00") -> Project:
    return Project(
        id="proj-1",
        user_id="owner-1",
        name="App",
        created_at="2025-12-01T00:00:00+00:00",
        published_url="my-app",
        published_at=published_at,
    )


@pytest.fixture
def record():
    with patch("flow44.api.page_views.increment_page_views", AsyncMock()) as mock_record:
        yield mock_record


@pytest.fixture
def bi_event():
    with patch("flow44.api.page_views.log_bi_event") as mock_log:
        yield mock_log


def _permissions(permissions):
    return patch("flow44.api.page_views.resolve_project_permissions", AsyncMock(return_value=permissions))


class TestTrackPageView:
    async def test_preview_resolves_project_by_id(self, record, bi_event):
        with (
            patch("flow44.api.page_views.get_project", AsyncMock(return_value=_project())) as mock_get,
            _permissions(get_owner_permissions()),
        ):
            response = client.post("/api/page-views", json={"source": "preview", "ref": "proj-1"})

        assert response.status_code == 204
        mock_get.assert_awaited_once_with("proj-1")
        record.assert_awaited_once_with("proj-1", PageViewSource.preview)
        bi_event.assert_called_once_with("page_viewed", view_source="preview", can_write=True)

    async def test_production_resolves_project_by_handle(self, record, bi_event):
        with (
            patch("flow44.api.page_views.get_project_by_handle", AsyncMock(return_value=_project())) as mock_get,
            _permissions(get_role_permissions(Role.viewer)),
        ):
            response = client.post("/api/page-views", json={"source": "production", "ref": "my-app"})

        assert response.status_code == 204
        mock_get.assert_awaited_once_with("my-app")
        record.assert_awaited_once_with("proj-1", PageViewSource.production)
        bi_event.assert_called_once_with("page_viewed", view_source="production", can_write=False)

    async def test_viewer_without_any_access_is_logged_as_read_only(self, record, bi_event):
        with (
            patch("flow44.api.page_views.get_project_by_handle", AsyncMock(return_value=_project())),
            _permissions(set()),
        ):
            response = client.post("/api/page-views", json={"source": "production", "ref": "my-app"})

        assert response.status_code == 204
        record.assert_awaited_once_with("proj-1", PageViewSource.production)
        bi_event.assert_called_once_with("page_viewed", view_source="production", can_write=False)

    async def test_unknown_project_returns_404(self, record, bi_event):
        with patch("flow44.api.page_views.get_project", AsyncMock(return_value=None)):
            response = client.post("/api/page-views", json={"source": "preview", "ref": "missing"})

        assert response.status_code == 404
        record.assert_not_awaited()
        bi_event.assert_not_called()

    async def test_unpublished_project_returns_404_for_production(self, record):
        with patch("flow44.api.page_views.get_project_by_handle", AsyncMock(return_value=_project(published_at=None))):
            response = client.post("/api/page-views", json={"source": "production", "ref": "my-app"})

        assert response.status_code == 404
        record.assert_not_awaited()

    async def test_invalid_source_returns_422(self, record):
        response = client.post("/api/page-views", json={"source": "staging", "ref": "proj-1"})

        assert response.status_code == 422
        record.assert_not_awaited()
