import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from flow44.api.deps import get_sandbox
from flow44.config import settings
from flow44.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_export_zip(tmp_path):
    project_id = "test-proj-123"
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    (workspace_dir / "file1.txt").write_text("content1")
    (workspace_dir / "subdir").mkdir()
    (workspace_dir / "subdir" / "file2.txt").write_text("content2")
    # node_modules should be excluded
    (workspace_dir / "node_modules").mkdir()
    (workspace_dir / "node_modules" / "secret.txt").write_text("secret")

    mock_sandbox = MagicMock()
    mock_sandbox.workspace_dir = str(workspace_dir)

    mock_project = AsyncMock()
    mock_project.name = "Test Project"

    app.dependency_overrides[get_sandbox] = lambda project_id: mock_sandbox
    try:
        with patch("flow44.api.export.get_project", return_value=mock_project):
            response = client.get(f"/api/export/{project_id}/zip")

            assert response.status_code == 200
            assert response.headers["Content-Type"] == "application/zip"
            assert 'attachment; filename="Test Project.zip"' in response.headers["Content-Disposition"]

            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                files = zf.namelist()
                assert "file1.txt" in files
                assert "subdir/file2.txt" in files
                assert "node_modules/secret.txt" not in files
                assert zf.read("file1.txt") == b"content1"
    finally:
        app.dependency_overrides.pop(get_sandbox, None)


@pytest.mark.asyncio
async def test_export_zip_no_sandbox():
    project_id = "no-sandbox"

    def _raise(project_id: str) -> None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project_id}")

    app.dependency_overrides[get_sandbox] = _raise
    try:
        response = client.get(f"/api/export/{project_id}/zip")
        assert response.status_code == 404
        assert "No sandbox found" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_sandbox, None)


@pytest.mark.asyncio
async def test_export_zip_missing_workspace(tmp_path):
    project_id = "missing-ws"
    workspace_dir = tmp_path / "not-here"
    mock_sandbox = MagicMock()
    mock_sandbox.workspace_dir = str(workspace_dir)

    app.dependency_overrides[get_sandbox] = lambda project_id: mock_sandbox
    try:
        response = client.get(f"/api/export/{project_id}/zip")
        assert response.status_code == 404
        assert response.json()["detail"] == "Workspace directory not found"
    finally:
        app.dependency_overrides.pop(get_sandbox, None)


@pytest.mark.asyncio
async def test_export_html():
    project_id = "test-proj-456"
    html_content = "<html><body>Hello World</body></html>"

    mock_project = AsyncMock()
    mock_project.name = "HTML Export"

    with (
        patch("flow44.api.export.build_single_html", return_value=html_content),
        patch("flow44.api.export.get_project", return_value=mock_project),
    ):
        response = client.get(f"/api/export/{project_id}/html")

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert 'attachment; filename="HTML Export.html"' in response.headers["Content-Disposition"]
        assert response.text == html_content


@pytest.mark.asyncio
async def test_export_html_error():
    project_id = "test-proj-err"

    with patch("flow44.api.export.build_single_html", side_effect=ValueError("No sandbox found")):
        response = client.get(f"/api/export/{project_id}/html")
        assert response.status_code == 404
        assert response.json()["detail"] == "No sandbox found"


@pytest.mark.asyncio
async def test_proxy_published_app_basic():
    project_id = "published-proj"
    mock_project = AsyncMock()
    mock_project.id = project_id
    mock_project.published_url = project_id
    mock_project.published_at = "2026-04-18T21:00:00Z"

    with patch("flow44.api.shared.get_project_by_handle", return_value=mock_project):
        with patch("flow44.api.shared.get_published_url", return_value="https://s3.local/published.html"):
            with patch("httpx.AsyncClient.get") as mock_get:
                mock_resp = AsyncMock()
                mock_resp.status_code = 200
                mock_resp.text = "<html>S3 Content</html>"
                mock_resp.headers = {"etag": "tag123"}
                mock_resp.raise_for_status = lambda: None
                mock_get.return_value = mock_resp

                response = client.get(f"/shared/{project_id}")

                assert response.status_code == 200
                assert response.text == "<html>S3 Content</html>"
                assert response.headers["ETag"] == "tag123"
                assert response.headers["Cache-Control"] == f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"


@pytest.mark.asyncio
async def test_proxy_published_app_fetch_error():
    project_id = "fetch-err"
    mock_project = AsyncMock()
    mock_project.id = project_id
    mock_project.published_url = project_id
    mock_project.published_at = "2026-04-18T21:00:00Z"

    with patch("flow44.api.shared.get_project_by_handle", return_value=mock_project):
        with patch("flow44.api.shared.get_published_url", return_value="https://s3.local/published.html"):
            with patch("httpx.AsyncClient.get", side_effect=Exception("S3 Down")):
                response = client.get(f"/shared/{project_id}")
                assert response.status_code == 502
                assert response.json()["detail"] == "Error fetching published app from S3."


@pytest.mark.asyncio
async def test_proxy_published_app_not_found():
    project_id = "non-existent"
    with patch("flow44.api.shared.get_project_by_handle", return_value=None):
        response = client.get(f"/shared/{project_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == f"No published app found for handle '{project_id}'."
