import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from flow44.api.deps import get_project, get_sandbox
from flow44.config import settings
from flow44.integrations.s3 import S3Object
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

    mock_project = MagicMock()
    mock_project.name = "Test Project"

    app.dependency_overrides[get_sandbox] = lambda: mock_sandbox
    app.dependency_overrides[get_project] = lambda: mock_project
    try:
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
        app.dependency_overrides.pop(get_project, None)


@pytest.mark.asyncio
async def test_export_zip_no_sandbox():
    project_id = "no-sandbox"

    mock_project = MagicMock()

    def _raise() -> None:
        raise HTTPException(status_code=404, detail=f"No sandbox found for project {project_id}")

    app.dependency_overrides[get_sandbox] = _raise
    app.dependency_overrides[get_project] = lambda: mock_project
    try:
        response = client.get(f"/api/export/{project_id}/zip")
        assert response.status_code == 404
        assert "No sandbox found" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_sandbox, None)
        app.dependency_overrides.pop(get_project, None)


@pytest.mark.asyncio
async def test_export_zip_missing_workspace(tmp_path):
    project_id = "missing-ws"
    workspace_dir = tmp_path / "not-here"
    mock_sandbox = MagicMock()
    mock_sandbox.workspace_dir = str(workspace_dir)

    mock_project = MagicMock()

    app.dependency_overrides[get_sandbox] = lambda: mock_sandbox
    app.dependency_overrides[get_project] = lambda: mock_project
    try:
        response = client.get(f"/api/export/{project_id}/zip")
        assert response.status_code == 404
        assert response.json()["detail"] == "Workspace directory not found"
    finally:
        app.dependency_overrides.pop(get_sandbox, None)
        app.dependency_overrides.pop(get_project, None)


@pytest.mark.asyncio
async def test_export_html():
    project_id = "test-proj-456"
    html_content = "<html><body>Hello World</body></html>"

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.name = "HTML Export"

    app.dependency_overrides[get_project] = lambda: mock_project
    try:
        with patch("flow44.api.export.build_single_html", return_value=html_content):
            response = client.get(f"/api/export/{project_id}/html")

            assert response.status_code == 200
            assert response.headers["Content-Type"] == "text/html; charset=utf-8"
            assert 'attachment; filename="HTML Export.html"' in response.headers["Content-Disposition"]
            assert response.text == html_content
    finally:
        app.dependency_overrides.pop(get_project, None)


@pytest.mark.asyncio
async def test_export_html_hebrew_name_does_not_crash():
    project_id = "test-proj-he"
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.name = "אפליקציה"

    app.dependency_overrides[get_project] = lambda: mock_project
    try:
        with patch("flow44.api.export.build_single_html", return_value="<html></html>"):
            response = client.get(f"/api/export/{project_id}/html")
    finally:
        app.dependency_overrides.pop(get_project, None)

    assert response.status_code == 200
    disposition = response.headers["Content-Disposition"]
    assert 'filename="export.html"' in disposition
    assert "filename*=UTF-8''" in disposition
    assert quote("אפליקציה.html", safe="") in disposition


@pytest.mark.asyncio
async def test_export_html_error():
    project_id = "test-proj-err"

    mock_project = MagicMock()
    mock_project.id = project_id

    app.dependency_overrides[get_project] = lambda: mock_project
    try:
        with patch("flow44.api.export.build_single_html", side_effect=ValueError("No sandbox found")):
            response = client.get(f"/api/export/{project_id}/html")
            assert response.status_code == 404
            assert response.json()["detail"] == "No sandbox found"
    finally:
        app.dependency_overrides.pop(get_project, None)


def _published_project(project_id: str = "proj-a"):
    return MagicMock(id=project_id, published_at="2026-04-18T21:00:00Z")


def _patch_serving(project, asset):
    return (
        patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=project)),
        patch("flow44.services.shared_service.s3_storage.get_asset", AsyncMock(return_value=asset)),
    )


@pytest.mark.asyncio
async def test_proxy_published_app_basic():
    asset = S3Object(body=b"<html>S3 Content</html>", content_type="text/html", etag="tag123")
    p_project, p_asset = _patch_serving(_published_project("published-proj"), asset)
    with p_project, p_asset:
        response = client.get("/shared/published-proj")

    assert response.status_code == 200
    assert response.text == "<html>S3 Content</html>"
    assert response.headers["ETag"] == "tag123"
    assert response.headers["Cache-Control"] == f"public, max-age={settings.S3_CACHE_TTL}, must-revalidate"


@pytest.mark.asyncio
async def test_proxy_published_app_not_found():
    with patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=None)):
        response = client.get("/shared/non-existent")
    assert response.status_code == 404
    assert response.json()["detail"] == "No published app found for handle 'non-existent'."


@pytest.mark.asyncio
async def test_proxy_asset_passes_through_content_type():
    asset = S3Object(body=b"\x89PNG\r\n\x1a\n", content_type="image/png", etag=None)
    p_project, p_asset = _patch_serving(_published_project(), asset)
    with p_project, p_asset:
        response = client.get("/shared/my-app/assets/logo.png")

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\n"
    assert response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_proxy_asset_rejects_traversal():
    from flow44.api.shared import proxy_published_asset  # noqa: PLC0415

    with pytest.raises(HTTPException) as exc:
        await proxy_published_asset(MagicMock(), "my-app", "../secret")
    assert exc.value.status_code == 400
