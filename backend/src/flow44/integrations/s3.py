import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from flow44.config import settings

logger = logging.getLogger(__name__)


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
        bucket_name = settings.S3_BUCKET_NAME

        async with contextlib.AsyncExitStack() as stack:
            if bucket_name:
                try:
                    self._client = await stack.enter_async_context(self._session.client("s3", **self._client_kwargs()))
                    stack.callback(setattr, self, "_client", None)
                    await self._ensure_bucket(bucket_name)
                    logger.info("S3 bucket setup complete.")
                except Exception as exc:
                    logger.warning("S3 setup issue (may already exist or be misconfigured): %s", exc)

            yield

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
    def _key(project_id: str) -> str:
        return f"published/{project_id}.html"

    def published_url(self, project_id: str) -> str:
        return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{self._key(project_id)}"

    async def deploy_single_html(self, html_content: str, project_id: str) -> str:
        await self.client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=self._key(project_id),
            Body=html_content.encode("utf-8"),
            ContentType="text/html",
            ACL="public-read",
            StorageClass=settings.S3_STORAGE_CLASS,
        )
        return self.published_url(project_id)

    async def delete_published_html(self, project_id: str) -> None:
        if not settings.S3_BUCKET_NAME:
            return
        key = self._key(project_id)
        try:
            await self.client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        except ClientError:
            logger.warning("Failed to delete S3 object %s", key)


s3_storage = S3Storage()
