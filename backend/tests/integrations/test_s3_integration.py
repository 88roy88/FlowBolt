from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from flow44.config import settings
from flow44.integrations.s3 import S3Storage


@pytest.fixture
def storage():
    return S3Storage()


@pytest.mark.asyncio
async def test_setup_opens_client_once(storage):
    client = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.client.return_value = cm

    storage._session = session
    with patch.object(S3Storage, "_ensure_bucket", AsyncMock()):
        await storage.setup("test-bucket")
        await storage.setup("test-bucket")

    assert storage.client is client
    assert session.client.call_count == 1


def test_client_requires_setup(storage):
    with pytest.raises(RuntimeError):
        _ = storage.client


@pytest.mark.asyncio
async def test_setup_ensures_bucket(storage):
    client = AsyncMock()
    storage._client = client
    bucket_name = "test-bucket"
    await storage.setup(bucket_name)

    client.create_bucket.assert_awaited_once_with(Bucket=bucket_name)
    client.put_bucket_policy.assert_awaited_once()
    _, kwargs = client.put_bucket_policy.call_args
    assert kwargs["Bucket"] == bucket_name
    assert "Statement" in kwargs["Policy"]


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
async def test_delete_published_html_no_bucket(storage):
    client = AsyncMock()
    storage._client = client
    with patch.object(settings, "S3_BUCKET_NAME", None):
        await storage.delete_published_html("proj-123")

        client.delete_object.assert_not_called()


@pytest.mark.asyncio
async def test_delete_published_html_swallows_client_error(storage):
    client = AsyncMock()
    client.delete_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "DeleteObject")
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.delete_published_html("proj-123")  # must not raise
