"""Tests for counting page views from the page requests the preview and /shared routes serve."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from flow44.api.deps import get_project, get_user_permissions
from flow44.auth.permissions import get_owner_permissions
from flow44.config import settings
from flow44.db.page_view import PageViewSource
from flow44.db.project import Project
from flow44.integrations.s3 import S3Object
from flow44.main import app
from flow44.services.logging import _user_id as _log_user_id

client = TestClient(app)

TAB = {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
IFRAME = {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "iframe"}
FETCH = {"Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"}


def _project() -> Project:
    return Project(
        id="proj-1",
        user_id="owner-1",
        name="App",
        created_at="2025-12-01T00:00:00+00:00",
        published_url="my-app",
        published_at="2026-01-01T00:00:00+00:00",
    )


def _asset(content_type: str = "text/html", path: str = "index.html") -> S3Object:
    return S3Object(path=path, body=b"<html></html>", content_type=content_type, etag='"abc"')


class TestPublishedAppViews:
    @pytest.fixture
    def record(self):
        with (
            patch("flow44.api.shared.get_project_by_handle", AsyncMock(return_value=_project())),
            patch("flow44.api.shared.record_page_view", AsyncMock()) as mock_record,
        ):
            yield mock_record

    def _get(self, path: str, headers: dict[str, str], asset: S3Object | None = None):
        with patch("flow44.api.shared.get_published_asset", AsyncMock(return_value=asset or _asset())):
            return client.get(f"/shared/my-app/{path}", headers=headers)

    @pytest.mark.parametrize("headers", [TAB, IFRAME], ids=["tab", "iframe"])
    def test_page_load_counts(self, record, headers):
        response = self._get("", headers)

        assert response.status_code == 200
        record.assert_awaited_once()
        project, source = record.await_args.args
        assert (project.id, source) == ("proj-1", PageViewSource.production)

    @pytest.mark.parametrize(
        ("payload", "user_id"),
        [(MagicMock(unique_id="user-1"), "user-1"), (None, None)],
        ids=["signed-in", "anonymous"],
    )
    def test_viewer_is_put_on_the_log(self, record, payload, user_id):
        logged_user_ids = []
        record.side_effect = lambda *_: logged_user_ids.append(_log_user_id.get())
        with patch("flow44.api.deps.decode_token", return_value=payload):
            self._get("", TAB | {"Cookie": f"{settings.AUTH_COOKIE_NAME}=token"})

        assert logged_user_ids == [user_id]

    def test_revalidated_page_load_counts(self, record):
        response = self._get("", TAB | {"If-None-Match": '"abc"'})

        assert response.status_code == 304
        record.assert_awaited_once()

    def test_fetch_does_not_count(self, record):
        self._get("", FETCH)
        record.assert_not_awaited()

    def test_asset_does_not_count(self, record):
        self._get("assets/index.js", TAB, _asset("application/javascript", "assets/index.js"))
        record.assert_not_awaited()


class TestPreviewViews:
    @pytest.fixture
    def record(self):
        sandbox = MagicMock(port=5173, is_dev_server_running=MagicMock(return_value=True))
        upstream = httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html></html>")
        app.dependency_overrides[get_project] = _project
        app.dependency_overrides[get_user_permissions] = get_owner_permissions
        try:
            with (
                patch("flow44.api.preview.sandbox_manager.wake_sandbox", AsyncMock(return_value=sandbox)),
                patch("flow44.api.preview._proxy_client.request", AsyncMock(return_value=upstream)),
                patch("flow44.api.preview.record_page_view", AsyncMock()) as mock_record,
            ):
                yield mock_record
        finally:
            app.dependency_overrides.pop(get_project, None)
            app.dependency_overrides.pop(get_user_permissions, None)

    def test_tab_counts(self, record):
        response = client.get("/api/preview/proj-1/proxy/", headers=TAB)

        assert response.status_code == 200
        record.assert_awaited_once()
        assert record.await_args.args[1] == PageViewSource.preview

    def test_builder_iframe_does_not_count(self, record):
        client.get("/api/preview/proj-1/proxy/", headers=IFRAME)
        record.assert_not_awaited()
