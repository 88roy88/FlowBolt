import functools
import json
import logging
import mimetypes
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from flow44.config import settings

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def connect_to_s3() -> Any:
    s3 = boto3.client(
        "s3",
        use_ssl=(settings.S3_ENDPOINT_URL or "").startswith("https://"),
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        endpoint_url=settings.S3_ENDPOINT_URL,
    )
    return s3


def setup_bucket(bucket_name: str) -> None:
    s3 = connect_to_s3()
    try:
        s3.create_bucket(Bucket=bucket_name)
        logger.info("Bucket '%s' created successfully.", bucket_name)
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
    s3.put_bucket_policy(
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


def _get_s3_key(project_id: str) -> str:
    return f"published/{project_id}.html"


def get_published_url(project_id: str) -> str:
    """Return the legacy single-HTML URL for a published project."""
    key = _get_s3_key(project_id)
    return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{key}"


def get_shared_asset_url(project_id: str, relative_path: str) -> str:
    # Legacy storage prefix kept for backward compatibility.
    key = f"published/{project_id}/{relative_path.lstrip('/')}"
    return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{key}"


def deploy_single_html(html_content: str, project_id: str) -> str:
    s3 = connect_to_s3()
    key = _get_s3_key(project_id)
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=html_content.encode("utf-8"),
        ContentType="text/html",
        ACL="public-read",
        StorageClass=settings.S3_STORAGE_CLASS,
    )
    return get_published_url(project_id)


def deploy_shared_dist(dist_dir: str, project_id: str) -> str:
    """Upload a Vite dist directory for shared serving."""
    s3 = connect_to_s3()
    for root, _, files in os.walk(dist_dir):
        for filename in files:
            absolute_path = os.path.join(root, filename)
            relative_path = os.path.relpath(absolute_path, dist_dir).replace(os.sep, "/")
            with open(absolute_path, "rb") as handle:
                s3.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    # Legacy storage prefix kept for backward compatibility.
                    Key=f"published/{project_id}/{relative_path}",
                    Body=handle.read(),
                    ContentType=mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    ACL="public-read",
                    StorageClass=settings.S3_STORAGE_CLASS,
                )
    return get_shared_asset_url(project_id, "index.html")
