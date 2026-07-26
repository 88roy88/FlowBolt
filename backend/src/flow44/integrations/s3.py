import contextlib
import json
import logging
import mimetypes
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from flow44.config import settings

logger = logging.getLogger(__name__)

_MISSING_OBJECT_CODES = {"NoSuchKey", "NoSuchBucket", "404"}


@dataclass(frozen=True)
class S3Object:
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
        await self.client.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(
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
            ),
        )

    @staticmethod
    def _prefix(project_id: str) -> str:
        return f"published/{project_id}/"

    async def deploy_dist(self, project_id: str, files: Iterable[tuple[str, bytes]]) -> None:
        await self.delete_published_prefix(project_id)
        for rel_path, body in files:
            content_type = mimetypes.guess_type(rel_path)[0] or "application/octet-stream"
            await self.client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=f"{self._prefix(project_id)}{rel_path}",
                Body=body,
                ContentType=content_type,
                ACL="public-read",
                StorageClass=settings.S3_STORAGE_CLASS,
            )

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
            body=await response["Body"].read(),
            content_type=response.get("ContentType") or "application/octet-stream",
            etag=response.get("ETag"),
        )

    async def delete_published_prefix(self, project_id: str) -> None:
        prefix = self._prefix(project_id)
        bucket = settings.S3_BUCKET_NAME
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if keys:
                    await self.client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
        except ClientError:
            logger.warning("Failed to delete S3 objects under %s", prefix)


s3_storage = S3Storage()
