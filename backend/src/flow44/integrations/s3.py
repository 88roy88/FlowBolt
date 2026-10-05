import contextlib
import itertools
import json
import logging
import mimetypes
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from flow44.config import settings

logger = logging.getLogger(__name__)

_MISSING_OBJECT_CODES = {"NoSuchKey", "NoSuchBucket", "404"}
_DELETE_BATCH_LIMIT = 1000
_DELETION_TAG = {"Key": "pending-deletion", "Value": "true"}
_DELETION_TAG_QUERY = f"{_DELETION_TAG['Key']}={_DELETION_TAG['Value']}"


def _content_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _public_read_policy(bucket_name: str) -> str:
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                }
            ],
        }
    )


def _delete_tagged_files_rule() -> dict[str, Any]:
    return {
        "Rules": [
            {
                "ID": "delete-pending-deletion",
                "Status": "Enabled",
                "Filter": {"Tag": _DELETION_TAG},
                "Expiration": {"Days": settings.S3_PENDING_DELETION_DAYS},
            }
        ]
    }


@dataclass(frozen=True)
class S3Object:
    path: str
    body: bytes
    content_type: str
    etag: str | None


class S3Storage:
    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._client: Any = None

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "use_ssl": settings.S3_USE_SSL,
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "endpoint_url": settings.S3_ENDPOINT_URL,
        }

    @property
    def client(self) -> Any:
        if self._client is None:
            raise RuntimeError("S3 client is not initialised; enter setup() during startup")
        return self._client

    @contextlib.asynccontextmanager
    async def setup(self) -> AsyncIterator[None]:
        async with self._session.client("s3", **self._client_kwargs()) as client:
            self._client = client
            await self._ensure_bucket(settings.S3_BUCKET_NAME)
            logger.info("S3 bucket setup complete.")
            try:
                yield
            finally:
                self._client = None

    async def _ensure_bucket(self, bucket_name: str) -> None:
        try:
            await self.client.create_bucket(Bucket=bucket_name)
            logger.info("Bucket '%s' created successfully.", bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise
        await self.client.put_bucket_policy(Bucket=bucket_name, Policy=_public_read_policy(bucket_name))
        await self.client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name, LifecycleConfiguration=_delete_tagged_files_rule()
        )

    @staticmethod
    def _prefix(project_id: str) -> str:
        return f"published/{project_id}/"

    async def deploy_dist(self, project_id: str, files: list[tuple[str, bytes]]) -> None:
        for rel_path, body in files:
            await self.client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=f"{self._prefix(project_id)}{rel_path}",
                Body=body,
                ContentType=_content_type(rel_path),
                ACL="public-read",
                StorageClass=settings.S3_STORAGE_CLASS,
            )
        await self.mark_old_files_for_deletion(project_id, {rel_path for rel_path, _ in files})

    async def get_asset(self, project_id: str, path: str) -> S3Object | None:
        try:
            response = await self.client.get_object(
                Bucket=settings.S3_BUCKET_NAME, Key=f"{self._prefix(project_id)}{path}"
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in _MISSING_OBJECT_CODES:
                return None
            raise
        return S3Object(
            path=path,
            body=await response["Body"].read(),
            content_type=response.get("ContentType") or "application/octet-stream",
            etag=response.get("ETag"),
        )

    async def _published_keys(self, project_id: str) -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=settings.S3_BUCKET_NAME, Prefix=self._prefix(project_id))
        return [obj["Key"] async for page in pages for obj in page.get("Contents", [])]

    async def mark_old_files_for_deletion(self, project_id: str, kept_paths: set[str]) -> None:
        prefix = self._prefix(project_id)
        try:
            for key in await self._published_keys(project_id):
                if key.removeprefix(prefix) not in kept_paths and not await self._is_pending_deletion(key):
                    await self._restart_clock_and_tag(key)
        except ClientError:
            logger.warning("Failed to mark old S3 objects for deletion under %s", prefix)

    async def _is_pending_deletion(self, key: str) -> bool:
        response = await self.client.get_object_tagging(Bucket=settings.S3_BUCKET_NAME, Key=key)
        return _DELETION_TAG in response["TagSet"]

    async def _restart_clock_and_tag(self, key: str) -> None:
        # Self-copy instead of put_object_tagging: lifecycle expiry counts from the last write, not from tagging.
        await self.client.copy_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            CopySource={"Bucket": settings.S3_BUCKET_NAME, "Key": key},
            MetadataDirective="REPLACE",
            ContentType=_content_type(key),
            TaggingDirective="REPLACE",
            Tagging=_DELETION_TAG_QUERY,
            ACL="public-read",
            StorageClass=settings.S3_STORAGE_CLASS,
        )

    async def delete_published_prefix(self, project_id: str) -> None:
        try:
            for batch in itertools.batched(await self._published_keys(project_id), _DELETE_BATCH_LIMIT, strict=False):
                await self.client.delete_objects(
                    Bucket=settings.S3_BUCKET_NAME, Delete={"Objects": [{"Key": key} for key in batch]}
                )
        except ClientError:
            logger.warning("Failed to delete S3 objects under %s", self._prefix(project_id))


s3_storage = S3Storage()
