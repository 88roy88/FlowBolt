"""Tests for slug-based publish, slug availability check, and share-by-slug proxy."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from flow44.api.deps import validate_token
from flow44.config import settings
from flow44.integrations.s3 import S3Object
from flow44.main import app

client = TestClient(app)


class TestSlugCheck:
    @pytest.mark.asyncio
    async def test_invalid_slug_returns_unavailable(self):
        response = client.get("/api/export/proj-1/slug/check?slug=A!")
        assert response.status_code == 200
        assert response.json() == {"available": False}

    @pytest.mark.asyncio
    async def test_taken_slug_returns_unavailable(self):
        with patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=True)):
            response = client.get("/api/export/proj-1/slug/check?slug=taken-slug")
            assert response.status_code == 200
            assert response.json() == {"available": False}

    @pytest.mark.asyncio
    async def test_free_slug_returns_available(self):
        with patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=False)):
            response = client.get("/api/export/proj-1/slug/check?slug=free-slug")
            assert response.status_code == 200
            assert response.json() == {"available": True}


class TestPublish:
    @pytest.fixture(autouse=True)
    def _override_project(self):
        from flow44.api.deps import get_project  # noqa: PLC0415

        project = MagicMock(id="proj-1")
        app.dependency_overrides[get_project] = lambda: project
        yield
        app.dependency_overrides.pop(get_project, None)

    @pytest.mark.asyncio
    async def test_publish_with_slug(self):
        with (
            patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=False)),
            patch("flow44.api.publish.publish_project", AsyncMock(return_value="my-cool-app")) as mock_publish,
        ):
            response = client.post("/api/export/proj-1/publish", json={"slug": "my-cool-app"})
            assert response.status_code == 200
            assert response.json() == {"url": "/shared/my-cool-app", "handle": "my-cool-app"}
            mock_publish.assert_awaited_once_with("proj-1", "my-cool-app")

    @pytest.mark.asyncio
    async def test_publish_without_slug(self):
        with patch("flow44.api.publish.publish_project", AsyncMock(return_value="proj-1")) as mock_publish:
            response = client.post("/api/export/proj-1/publish", json={"slug": None})
            assert response.status_code == 200
            assert response.json() == {"url": "/shared/proj-1", "handle": "proj-1"}
            mock_publish.assert_awaited_once_with("proj-1", None)

    @pytest.mark.asyncio
    async def test_publish_with_taken_slug_returns_409(self):
        with patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=True)):
            response = client.post("/api/export/proj-1/publish", json={"slug": "taken-slug"})
            assert response.status_code == 409
            assert "already taken" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_publish_with_invalid_slug_returns_400(self):
        response = client.post("/api/export/proj-1/publish", json={"slug": "X!"})
        assert response.status_code == 400
        assert "Invalid slug" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_publish_collision_returns_409(self):
        with (
            patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=False)),
            patch(
                "flow44.api.publish.publish_project",
                AsyncMock(side_effect=IntegrityError(None, None, Exception("collision"))),
            ),
        ):
            response = client.post("/api/export/proj-1/publish", json={"slug": "collision-slug"})
            assert response.status_code == 409
            assert "just claimed" in response.json()["detail"]


class TestShareBySlug:
    @staticmethod
    def _patch_serving(project, asset):
        return (
            patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=project)),
            patch("flow44.services.shared_service.s3_storage.get_asset", AsyncMock(return_value=asset)),
        )

    @pytest.mark.asyncio
    async def test_share_returns_proxied_html(self):
        project = MagicMock(id="proj-123", published_at="2026-04-18T21:00:00Z")
        asset = S3Object(body=b"<html>Shared App</html>", content_type="text/html", etag='"abc"')
        p_project, p_asset = self._patch_serving(project, asset)
        with p_project, p_asset:
            response = client.get("/shared/my-app")

        assert response.status_code == 200
        assert response.text == "<html>Shared App</html>"
        assert response.headers["Cache-Control"] == f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"
        assert response.headers["ETag"] == '"abc"'

    @pytest.mark.asyncio
    async def test_share_unknown_slug_returns_404(self):
        with patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=None)):
            response = client.get("/shared/nonexistent")
            assert response.status_code == 404
            assert "No published app found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_share_route_is_public(self):
        """The share route must serve without a token — it backs public links."""
        project = MagicMock(id="proj-123", published_at="2026-04-18T21:00:00Z")
        asset = S3Object(body=b"<html>Shared App</html>", content_type="text/html", etag=None)
        saved = app.dependency_overrides.pop(validate_token, None)
        try:
            p_project, p_asset = self._patch_serving(project, asset)
            with p_project, p_asset:
                response = client.get("/shared/my-app")
                assert response.status_code == 200
                assert response.text == "<html>Shared App</html>"
        finally:
            if saved is not None:
                app.dependency_overrides[validate_token] = saved
