from unittest.mock import AsyncMock, patch

import pytest

from flow44.logic.publish import (
    SlugStatus,
    publish_project,
    resolve_slug_status,
)


@pytest.mark.asyncio
async def test_resolve_slug_status_invalid():
    assert await resolve_slug_status("A!", "proj-1") == SlugStatus.invalid


@pytest.mark.asyncio
async def test_resolve_slug_status_taken():
    with patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=True)):
        assert await resolve_slug_status("my-slug", "proj-1") == SlugStatus.taken


@pytest.mark.asyncio
async def test_resolve_slug_status_available():
    with patch("flow44.logic.publish.is_handle_taken", AsyncMock(return_value=False)):
        assert await resolve_slug_status("my-slug", "proj-1") == SlugStatus.available


@pytest.mark.asyncio
async def test_publish_project_deploys_and_sets_handle():
    files = [("index.html", b"<html></html>")]
    with (
        patch("flow44.logic.publish.build_dist", AsyncMock(return_value=files)) as p_build,
        patch("flow44.logic.publish.s3_storage.deploy_dist", AsyncMock()) as p_deploy,
        patch("flow44.logic.publish.update_project_published_url", AsyncMock()) as p_update,
    ):
        handle = await publish_project("proj-1", "my-slug")

    assert handle == "my-slug"
    p_build.assert_awaited_once_with("proj-1")
    p_deploy.assert_awaited_once_with("proj-1", files)
    p_update.assert_awaited_once_with("proj-1", "my-slug")


@pytest.mark.asyncio
async def test_publish_project_defaults_handle_to_project_id():
    with (
        patch("flow44.logic.publish.build_dist", AsyncMock(return_value=[])),
        patch("flow44.logic.publish.s3_storage.deploy_dist", AsyncMock()),
        patch("flow44.logic.publish.update_project_published_url", AsyncMock()) as p_update,
    ):
        handle = await publish_project("proj-1", None)

    assert handle == "proj-1"
    p_update.assert_awaited_once_with("proj-1", "proj-1")
