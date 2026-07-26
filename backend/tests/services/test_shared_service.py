from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flow44.integrations.s3 import S3Object
from flow44.services.shared_service import AppNotPublishedError, get_published_asset


def _published_project():
    return MagicMock(id="proj-1", published_at="2026-04-18T21:00:00Z")


def _asset(content_type="text/html"):
    return S3Object(body=b"data", content_type=content_type, etag=None)


@pytest.mark.asyncio
async def test_unknown_handle_raises():
    with patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=None)):
        with pytest.raises(AppNotPublishedError):
            await get_published_asset("nope", "index.html")


@pytest.mark.asyncio
async def test_returns_asset():
    asset = _asset("image/png")
    with (
        patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=_published_project())),
        patch("flow44.services.shared_service.s3_storage.get_asset", AsyncMock(return_value=asset)) as p_get,
    ):
        result = await get_published_asset("my-app", "logo.png")

    assert result is asset
    p_get.assert_awaited_once_with("proj-1", "logo.png")


@pytest.mark.asyncio
async def test_spa_fallback_serves_index_for_extensionless_route():
    index = _asset()
    with (
        patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=_published_project())),
        patch(
            "flow44.services.shared_service.s3_storage.get_asset",
            AsyncMock(side_effect=[None, index]),
        ) as p_get,
    ):
        result = await get_published_asset("my-app", "about")

    assert result is index
    assert p_get.await_args_list[-1].args == ("proj-1", "index.html")


@pytest.mark.asyncio
async def test_missing_asset_with_extension_returns_none():
    with (
        patch("flow44.services.shared_service.get_project_by_handle", AsyncMock(return_value=_published_project())),
        patch("flow44.services.shared_service.s3_storage.get_asset", AsyncMock(return_value=None)) as p_get,
    ):
        result = await get_published_asset("my-app", "missing.png")

    assert result is None
    p_get.assert_awaited_once_with("proj-1", "missing.png")
