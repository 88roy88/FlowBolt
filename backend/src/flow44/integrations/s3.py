import contextlib
import json
import logging
from typing import Any

import aioboto3
from botocore.exceptions import ClientError

from flow44.config import settings

logger = logging.getLogger(__name__)


class S3Storage:
    """Manages the shared aioboto3 S3 client and published-app storage.

    The client is opened once at startup (`setup`) and closed at shutdown
    (`close`), then reused across requests.
    """

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._client: Any = None
        self._exit_stack: contextlib.AsyncExitStack | None = None

    def _client_kwargs(self) -> dict[str, Any]:
        return {
            "use_ssl": (settings.S3_ENDPOINT_URL or "").startswith("https://"),
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "endpoint_url": settings.S3_ENDPOINT_URL,
        }

    @property
    def client(self) -> Any:
        """The shared S3 client. Requires `setup` to have run at startup."""
        if self._client is None:
            raise RuntimeError("S3 client is not initialised; call setup() at startup")
        return self._client

    async def init(self) -> None:
        """Open the shared S3 client. Idempotent."""
        if self._client is not None:
            return
        self._exit_stack = contextlib.AsyncExitStack()
        self._client = await self._exit_stack.enter_async_context(self._session.client("s3", **self._client_kwargs()))

    async def setup(self, bucket_name: str) -> None:
        """Open the client and ensure the bucket exists. Call once on startup."""
        await self.init()
        await self._ensure_bucket(bucket_name)

    async def close(self) -> None:
        """Close the shared S3 client. Call once on application shutdown."""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
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
    def _key(project_id: str) -> str:
        return f"published/{project_id}.html"

    def published_url(self, project_id: str) -> str:
        """Return the internal S3 URL for a published project."""
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
        """Remove a project's published HTML from S3. Best-effort; never raises."""
        if not settings.S3_BUCKET_NAME:
            return
        key = self._key(project_id)
        try:
            await self.client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        except ClientError:
            logger.warning("Failed to delete S3 object %s", key)


s3_storage = S3Storage()
