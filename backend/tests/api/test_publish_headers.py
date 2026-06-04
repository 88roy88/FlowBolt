from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.config import settings
from flow44.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_proxy_published_app_headers():
    project_id = "test-project"
    mock_project = AsyncMock()
    mock_project.id = project_id
    mock_project.published_url = project_id
    mock_project.published_at = "2015-10-21T07:28:00Z"

    with patch("flow44.api.shared.get_project_by_handle", return_value=mock_project):
        with patch("flow44.api.shared.get_published_url", return_value="https://example.com/index.html"):
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status_code = 200
                mock_resp.text = "<html>Testing headers</html>"
                mock_resp.headers = {"etag": '"12345"', "last-modified": "Wed, 21 Oct 2015 07:28:00 GMT"}
                mock_resp.raise_for_status = lambda: None
                mock_get.return_value = mock_resp

                response = client.get(f"/shared/{project_id}")

                assert response.status_code == 200
                assert response.headers["Cache-Control"] == f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"
                assert response.headers["ETag"] == '"12345"'
                assert response.headers["Last-Modified"] == "Wed, 21 Oct 2015 07:28:00 GMT"
                assert response.text == "<html>Testing headers</html>"
