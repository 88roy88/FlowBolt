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


def _mock_paginator(client, pages):
    async def _paginate(**_kwargs):
        for page in pages:
            yield page

    paginator = MagicMock()
    paginator.paginate = _paginate
    client.get_paginator = MagicMock(return_value=paginator)


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

    with (
        patch.object(settings, "S3_BUCKET_NAME", bucket_name),
        patch.object(settings, "S3_UPLOADS_BUCKET_NAME", "test-uploads"),
    ):
        async with storage.setup():
            assert [c.kwargs for c in client.create_bucket.await_args_list] == [
                {"Bucket": bucket_name},
                {"Bucket": "test-uploads"},
            ]
            # The uploads bucket stays private and keeps its files.
            client.put_bucket_policy.assert_awaited_once()
            client.put_bucket_lifecycle_configuration.assert_awaited_once()
            _, kwargs = client.put_bucket_policy.call_args
            assert kwargs["Bucket"] == bucket_name
            assert "Statement" in kwargs["Policy"]
            [rule] = client.put_bucket_lifecycle_configuration.call_args.kwargs["LifecycleConfiguration"]["Rules"]
            assert rule["Filter"] == {"Tag": {"Key": "pending-deletion", "Value": "true"}}
            assert rule["Expiration"] == {"Days": 7}


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
async def test_deploy_dist(storage):
    client = AsyncMock()
    _mock_paginator(client, [])
    storage._client = client
    files = [
        ("index.html", b"<html></html>"),
        ("assets/app-abc.js", b"console.log(1)"),
        ("logo.png", b"\x89PNG"),
    ]

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.deploy_dist("proj-123", files)

    calls = {c.kwargs["Key"]: c.kwargs for c in client.put_object.call_args_list}
    assert set(calls) == {
        "published/proj-123/index.html",
        "published/proj-123/assets/app-abc.js",
        "published/proj-123/logo.png",
    }
    assert calls["published/proj-123/index.html"]["ContentType"] == "text/html"
    assert calls["published/proj-123/logo.png"]["ContentType"] == "image/png"
    assert calls["published/proj-123/index.html"]["ACL"] == "public-read"


@pytest.mark.asyncio
async def test_deploy_dist_tags_only_newly_dropped_files(storage):
    client = AsyncMock()
    keys = ["index.html", "already-pending.js", "dropped.png"]
    _mock_paginator(client, [{"Contents": [{"Key": f"published/proj-123/{key}"} for key in keys]}])
    deletion_tag = {"Key": "pending-deletion", "Value": "true"}
    client.get_object_tagging.side_effect = lambda Key, **_: {
        "TagSet": [deletion_tag] if Key.endswith("already-pending.js") else []
    }
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.deploy_dist("proj-123", [("index.html", b"<html></html>")])

    client.copy_object.assert_awaited_once()
    copy = client.copy_object.call_args.kwargs
    assert copy["Key"] == "published/proj-123/dropped.png"
    assert copy["CopySource"] == {"Bucket": "my-bucket", "Key": "published/proj-123/dropped.png"}
    assert copy["Tagging"] == "pending-deletion=true"
    assert copy["ContentType"] == "image/png"
    client.delete_objects.assert_not_awaited()


@pytest.mark.asyncio
async def test_deploy_dist_survives_tagging_error(storage):
    client = AsyncMock()
    _mock_paginator(client, [{"Contents": [{"Key": "published/proj-123/old.png"}]}])
    client.get_object_tagging.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetObjectTagging")
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.deploy_dist("proj-123", [("index.html", b"<html></html>")])

    client.put_object.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_published_prefix(storage):
    client = AsyncMock()
    _mock_paginator(
        client,
        [{"Contents": [{"Key": "published/proj-123/index.html"}, {"Key": "published/proj-123/logo.png"}]}],
    )
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.delete_published_prefix("proj-123")

    client.get_paginator.assert_called_once_with("list_objects_v2")
    client.delete_objects.assert_awaited_once_with(
        Bucket="my-bucket",
        Delete={"Objects": [{"Key": "published/proj-123/index.html"}, {"Key": "published/proj-123/logo.png"}]},
    )


@pytest.mark.asyncio
async def test_delete_published_prefix_empty_is_noop(storage):
    client = AsyncMock()
    _mock_paginator(client, [{"Contents": []}])
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.delete_published_prefix("proj-123")

    client.delete_objects.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_published_prefix_swallows_client_error(storage):
    client = AsyncMock()
    client.get_paginator = MagicMock(side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "ListObjectsV2"))
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        await storage.delete_published_prefix("proj-123")  # must not raise


@pytest.mark.asyncio
async def test_get_asset_returns_s3object(storage):
    client = AsyncMock()
    body = AsyncMock()
    body.read = AsyncMock(return_value=b"\x89PNG")
    client.get_object = AsyncMock(
        return_value={
            "Body": body,
            "ContentType": "image/png",
            "ETag": '"abc"',
        }
    )
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        obj = await storage.get_asset("proj-123", "logo.png")

    client.get_object.assert_awaited_once_with(Bucket="my-bucket", Key="published/proj-123/logo.png")
    assert obj is not None
    assert obj.path == "logo.png"
    assert obj.body == b"\x89PNG"
    assert obj.content_type == "image/png"
    assert obj.etag == '"abc"'


@pytest.mark.asyncio
async def test_get_asset_missing_returns_none(storage):
    client = AsyncMock()
    client.get_object = AsyncMock(side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject"))
    storage._client = client

    with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
        assert await storage.get_asset("proj-123", "missing.png") is None


async def _chunks(*parts: bytes):
    for part in parts:
        yield part


def _multipart_client() -> AsyncMock:
    client = AsyncMock()
    client.create_multipart_upload = AsyncMock(return_value={"UploadId": "up-1"})
    client.upload_part = AsyncMock(side_effect=lambda **kw: {"ETag": f"etag-{kw['PartNumber']}"})
    return client


@pytest.mark.asyncio
async def test_upload_stream_rechunks_into_parts(storage):
    client = _multipart_client()
    storage._client = client

    with (
        patch.object(settings, "S3_UPLOADS_BUCKET_NAME", "uploads"),
        patch("flow44.integrations.s3._MULTIPART_PART_SIZE", 4),
    ):
        size = await storage.upload_stream("k", _chunks(b"abc", b"defgh", b"ij"), "image/png")

    assert size == 10
    assert [c.kwargs["Body"] for c in client.upload_part.await_args_list] == [b"abcd", b"efgh", b"ij"]
    client.create_multipart_upload.assert_awaited_once_with(Bucket="uploads", Key="k", ContentType="image/png")
    parts = client.complete_multipart_upload.await_args.kwargs["MultipartUpload"]["Parts"]
    assert parts == [{"PartNumber": n, "ETag": f"etag-{n}"} for n in (1, 2, 3)]


@pytest.mark.asyncio
async def test_upload_stream_of_an_empty_file_sends_one_empty_part(storage):
    client = _multipart_client()
    storage._client = client

    assert await storage.upload_stream("k", _chunks(), "text/plain") == 0
    assert [c.kwargs["Body"] for c in client.upload_part.await_args_list] == [b""]
    client.complete_multipart_upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_stream_aborts_when_the_source_fails(storage):
    client = _multipart_client()
    storage._client = client

    async def failing():
        yield b"abc"
        raise ValueError("client went away")

    with pytest.raises(ValueError, match="client went away"):
        await storage.upload_stream("k", failing(), "image/png")

    client.abort_multipart_upload.assert_awaited_once()
    client.complete_multipart_upload.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_upload_missing_returns_none(storage):
    client = AsyncMock()
    client.get_object = AsyncMock(side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject"))
    storage._client = client

    assert await storage.read_upload("missing") is None
