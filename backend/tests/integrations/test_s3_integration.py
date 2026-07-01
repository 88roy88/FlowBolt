from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from flow44.config import settings
from flow44.integrations.s3 import S3Storage


@pytest.fixture
def storage():
    return S3Storage()


def _mock_client_cm(client):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def test_client_requires_setup(storage):
    with pytest.raises(RuntimeError):
        _ = storage.client


@pytest.mark.asyncio
async def test_setup_opens_and_closes_client(storage):
    client = AsyncMock()
    cm = _mock_client_cm(client)
    session = MagicMock()
    session.client.return_value = cm
    storage._session = session

    with patch.object(settings, "S3_BUCKET_NAME", "test-bucket"):
        with patch.object(S3Storage, "_ensure_bucket", AsyncMock()):
            async with storage.setup():
                assert storage.client is client

    cm.__aexit__.assert_awaited_once()
    with pytest.raises(RuntimeError):
        _ = storage.client


@pytest.mark.asyncio
async def test_setup_ensures_bucket(storage):
    client = AsyncMock()
    cm = _mock_client_cm(client)
    session = MagicMock()
    session.client.return_value = cm
    storage._session = session
    bucket_name = "test-bucket"

    with patch.object(settings, "S3_BUCKET_NAME", bucket_name):
        async with storage.setup():
            client.create_bucket.assert_awaited_once_with(Bucket=bucket_name)
            client.put_bucket_policy.assert_awaited_once()
            _, kwargs = client.put_bucket_policy.call_args
            assert kwargs["Bucket"] == bucket_name
            assert "Statement" in kwargs["Policy"]


@pytest.mark.asyncio
async def test_setup_propagates_ensure_bucket_failure(storage):
    client = AsyncMock()
    cm = _mock_client_cm(client)
    session = MagicMock()
    session.client.return_value = cm
    storage._session = session

    with patch.object(settings, "S3_BUCKET_NAME", "test-bucket"):
        with patch.object(S3Storage, "_ensure_bucket", AsyncMock(side_effect=RuntimeError("boom"))):
            with pytest.raises(RuntimeError, match="boom"):
                async with storage.setup():
                    pass

    cm.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_propagates_acquisition_failure(storage):
    session = MagicMock()
    session.client.side_effect = RuntimeError("connection failed")
    storage._session = session

    with patch.object(settings, "S3_BUCKET_NAME", "test-bucket"):
        with pytest.raises(RuntimeError, match="connection failed"):
            async with storage.setup():
                pass


@pytest.mark.asyncio
async def test_setup_propagates_close_error(storage):
    client = AsyncMock()
    cm = _mock_client_cm(client)
    cm.__aexit__ = AsyncMock(side_effect=RuntimeError("close failed"))
    session = MagicMock()
    session.client.return_value = cm
    storage._session = session

    with patch.object(settings, "S3_BUCKET_NAME", "test-bucket"):
        with patch.object(S3Storage, "_ensure_bucket", AsyncMock()):
            with pytest.raises(RuntimeError, match="close failed"):
                async with storage.setup():
                    pass

    with pytest.raises(RuntimeError):
        _ = storage.client


@pytest.mark.asyncio
async def test_deploy_single_html(storage):
    client = AsyncMock()
    storage._client = client
    html_content = "<html>test</html>"
    project_id = "proj-123"

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        with patch.object(settings, "S3_ENDPOINT_URL", "http://s3.local"):
            url = await storage.deploy_single_html(html_content, project_id)

            expected_key = f"published/{project_id}.html"
            client.put_object.assert_awaited_once_with(
                Bucket="my-bucket",
                Key=expected_key,
                Body=html_content.encode("utf-8"),
                ContentType="text/html",
                ACL="public-read",
                StorageClass=settings.S3_STORAGE_CLASS,
            )
            assert url == f"http://s3.local/my-bucket/{expected_key}"


@pytest.mark.asyncio
async def test_delete_published_html(storage):
    client = AsyncMock()
    storage._client = client
    project_id = "proj-123"

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.delete_published_html(project_id)

        client.delete_object.assert_awaited_once_with(
            Bucket="my-bucket", Key=f"published/{project_id}.html"
        )


@pytest.mark.asyncio
async def test_delete_published_html_swallows_client_error(storage):
    client = AsyncMock()
    client.delete_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "DeleteObject")
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.delete_published_html("proj-123")  # must not raise
