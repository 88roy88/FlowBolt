import functools
import json
import logging
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


def deploy_single_html(html_content: str, project_id: str) -> str:
    """Deploy a single HTML string to S3 and return the public URL."""
    s3 = connect_to_s3()
    key = f"published/{project_id}.html"
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=html_content.encode("utf-8"),
        ContentType="text/html",
        ACL="public-read",
    )
    return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{key}"
