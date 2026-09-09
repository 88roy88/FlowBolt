from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.config import settings
from flow44.integrations.s3 import S3Object
from flow44.main import app

client = TestClient(app)


def _serve(asset):
    project = MagicMock(id="test-project", published_at="2015-10-21T07:28:00Z")
    return (
        patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=project)),
        patch("flow44.services.shared_service.s3_storage.get_asset", AsyncMock(return_value=asset)),
    )


@pytest.mark.asyncio
async def test_proxy_published_app_headers():
    asset = S3Object(body=b"<html>Testing headers</html>", content_type="text/html", etag='"12345"')

    p_project, p_asset = _serve(asset)
    with p_project, p_asset:
        response = client.get("/shared/test-project")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"
    assert response.headers["ETag"] == '"12345"'
    assert "Last-Modified" not in response.headers
    assert response.text == "<html>Testing headers</html>"


@pytest.mark.asyncio
async def test_matching_if_none_match_returns_304():
    asset = S3Object(body=b"<html>Testing headers</html>", content_type="text/html", etag='"12345"')

    p_project, p_asset = _serve(asset)
    with p_project, p_asset:
        response = client.get("/shared/test-project", headers={"If-None-Match": '"12345"'})

    assert response.status_code == 304
    assert response.headers["ETag"] == '"12345"'
    assert response.content == b""


@pytest.mark.asyncio
async def test_stale_if_none_match_returns_200():
    asset = S3Object(body=b"<html>Testing headers</html>", content_type="text/html", etag='"12345"')

    p_project, p_asset = _serve(asset)
    with p_project, p_asset:
        response = client.get("/shared/test-project", headers={"If-None-Match": '"old"'})

    assert response.status_code == 200
    assert response.text == "<html>Testing headers</html>"
