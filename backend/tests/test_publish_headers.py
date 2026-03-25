import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from flow44.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_proxy_published_app_headers():
    project_id = "test-project"
    mock_project = AsyncMock()
    mock_project.published_url = "https://example.com/index.html"
    
    with patch("flow44.api.publish.get_project", return_value=mock_project):
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.text = "<html>Testing headers</html>"
            mock_resp.headers = {
                "etag": '"12345"',
                "last-modified": "Wed, 21 Oct 2015 07:28:00 GMT"
            }
            mock_resp.raise_for_status = lambda: None
            mock_get.return_value = mock_resp
            
            response = client.get(f"/api/export/{project_id}/published")
            
            assert response.status_code == 200
            assert response.headers["Cache-Control"] == "public, max-age=0, must-revalidate"
            assert response.headers["ETag"] == '"12345"'
            assert response.headers["Last-Modified"] == "Wed, 21 Oct 2015 07:28:00 GMT"
            assert response.text == "<html>Testing headers</html>"
