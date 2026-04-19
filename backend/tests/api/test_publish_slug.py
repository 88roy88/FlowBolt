"""Tests for slug-based publish, slug availability check, and share-by-slug proxy."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from flow44.config import settings
from flow44.main import app

client = TestClient(app)

MOCK_S3_URL = "https://s3.local/bucket/published/proj-1.html"


def _mock_project(published_url: str = "", published_at: str | None = None):
    proj = AsyncMock()
    proj.published_url = published_url
    proj.published_at = published_at
    return proj


# ---------------------------------------------------------------------------
# GET /api/export/{project_id}/slug/check
# ---------------------------------------------------------------------------


class TestSlugCheck:
    @pytest.mark.asyncio
    async def test_invalid_slug_returns_unavailable(self):
        response = client.get("/api/export/proj-1/slug/check?slug=A!")
        assert response.status_code == 200
        assert response.json() == {"available": False}

    @pytest.mark.asyncio
    async def test_taken_slug_returns_unavailable(self):
        with patch("flow44.api.publish.is_handle_taken", return_value=True):
            response = client.get("/api/export/proj-1/slug/check?slug=taken-slug")
            assert response.status_code == 200
            assert response.json() == {"available": False}

    @pytest.mark.asyncio
    async def test_free_slug_returns_available(self):
        with patch("flow44.api.publish.is_handle_taken", return_value=False):
            response = client.get("/api/export/proj-1/slug/check?slug=free-slug")
            assert response.status_code == 200
            assert response.json() == {"available": True}


# ---------------------------------------------------------------------------
# POST /api/export/{project_id}/publish
# ---------------------------------------------------------------------------


class TestPublish:
    def _patch_build_and_deploy(self):
        return (
            patch("flow44.api.publish.build_single_html", return_value="<html>ok</html>"),
            patch("flow44.api.publish.deploy_single_html", return_value=MOCK_S3_URL),
            patch.object(settings, "S3_BUCKET_NAME", "test-bucket"),
        )

    @pytest.mark.asyncio
    async def test_publish_with_slug(self):
        p_build, p_deploy, p_bucket = self._patch_build_and_deploy()
        with (
            p_build,
            p_deploy,
            p_bucket,
            patch("flow44.api.publish.is_handle_taken", return_value=False),
            patch("flow44.api.publish.update_project_published_url", return_value="2026-04-19T12:00:00Z") as mock_update,
        ):
            response = client.post(
                "/api/export/proj-1/publish",
                json={"slug": "my-cool-app"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["url"] == "/shared/my-cool-app"
            assert data["handle"] == "my-cool-app"
            mock_update.assert_awaited_once_with("proj-1", "my-cool-app")

    @pytest.mark.asyncio
    async def test_publish_without_slug(self):
        p_build, p_deploy, p_bucket = self._patch_build_and_deploy()
        with (
            p_build,
            p_deploy,
            p_bucket,
            patch("flow44.api.publish.update_project_published_url", return_value="2026-04-19T12:00:00Z") as mock_update,
        ):
            response = client.post(
                "/api/export/proj-1/publish",
                json={"slug": None},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["url"] == "/shared/proj-1"
            assert data["handle"] == "proj-1"
            mock_update.assert_awaited_once_with("proj-1", "proj-1")

    @pytest.mark.asyncio
    async def test_publish_with_taken_slug_returns_409(self):
        p_build, p_deploy, p_bucket = self._patch_build_and_deploy()
        with (
            p_build,
            p_deploy,
            p_bucket,
            patch("flow44.api.publish.is_handle_taken", return_value=True),
        ):
            response = client.post(
                "/api/export/proj-1/publish",
                json={"slug": "taken-slug"},
            )
            assert response.status_code == 409
            assert "already taken" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_republish_same_slug_succeeds(self):
        """Re-publishing with the project's own slug should pass (is_slug_taken excludes self)."""
        p_build, p_deploy, p_bucket = self._patch_build_and_deploy()
        with (
            p_build,
            p_deploy,
            p_bucket,
            patch("flow44.api.publish.is_handle_taken", return_value=False),
            patch("flow44.api.publish.update_project_published_url", return_value="2026-04-19T12:00:00Z"),
        ):
            response = client.post(
                "/api/export/proj-1/publish",
                json={"slug": "existing-slug"},
            )
            assert response.status_code == 200
            assert response.json()["url"] == "/shared/existing-slug"

    @pytest.mark.asyncio
    async def test_publish_with_invalid_slug_returns_400(self):
        p_build, p_deploy, p_bucket = self._patch_build_and_deploy()
        with p_build, p_deploy, p_bucket:
            response = client.post(
                "/api/export/proj-1/publish",
                json={"slug": "X!"},
            )
            assert response.status_code == 400
            assert "Invalid slug" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_publish_collision_returns_409(self):
        """Test that if the handle is claimed after check but before update, 409 is returned."""
        p_build, p_deploy, p_bucket = self._patch_build_and_deploy()
        with (
            p_build,
            p_deploy,
            p_bucket,
            patch("flow44.api.publish.is_handle_taken", return_value=False),
            patch(
                "flow44.api.publish.update_project_published_url",
                side_effect=IntegrityError(None, None, Exception("collision")),
            ),
        ):
            response = client.post(
                "/api/export/proj-1/publish",
                json={"slug": "collision-slug"},
            )
            assert response.status_code == 409
            assert "just claimed by another project" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /shared/{slug}
# ---------------------------------------------------------------------------


class TestShareBySlug:
    @pytest.mark.asyncio
    async def test_share_returns_proxied_html(self):
        mock_proj = _mock_project(published_url="my-app", published_at="2026-04-18T21:00:00Z")
        mock_proj.id = "proj-123"
        with patch("flow44.api.shared.get_project_by_handle", return_value=mock_proj):
            with patch("flow44.api.shared.get_published_url", return_value="https://s3.local/proj-123.html"), \
                 patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status_code = 200
                mock_resp.text = "<html>Shared App</html>"
                mock_resp.headers = {
                    "etag": '"abc"',
                    "last-modified": "Thu, 10 Apr 2026 12:00:00 GMT",
                }
                mock_resp.raise_for_status = lambda: None
                mock_get.return_value = mock_resp

                response = client.get("/shared/my-app")

                assert response.status_code == 200
                assert response.text == "<html>Shared App</html>"
                assert response.headers["Cache-Control"] == f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"
                assert response.headers["ETag"] == '"abc"'
                assert response.headers["Last-Modified"] == "Thu, 10 Apr 2026 12:00:00 GMT"

    @pytest.mark.asyncio
    async def test_share_unknown_slug_returns_404(self):
        with patch("flow44.api.shared.get_project_by_handle", return_value=None):
            response = client.get("/shared/nonexistent")
            assert response.status_code == 404
            assert "No published app found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_share_s3_failure_returns_502(self):
        mock_proj = _mock_project(published_url="my-app", published_at="2026-04-18T21:00:00Z")
        mock_proj.id = "proj-123"
        with patch("flow44.api.shared.get_project_by_handle", return_value=mock_proj):
            with patch("flow44.api.shared.get_published_url", return_value="https://s3.local/proj-123.html"), \
                 patch("httpx.AsyncClient.get", side_effect=Exception("S3 down")):
                response = client.get("/shared/my-app")
                assert response.status_code == 502
                assert "Error fetching published app" in response.json()["detail"]
