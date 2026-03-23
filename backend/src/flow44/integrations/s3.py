import json
import mimetypes
import os
import zipfile
from typing import Any

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
SECRET_KEY = os.getenv("S3_SECRET_KEY")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


def connect_to_s3() -> Any:
    s3 = boto3.client(
        "s3",
        use_ssl=(ENDPOINT_URL or "").startswith("https://"),
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        endpoint_url=ENDPOINT_URL,
    )
    return s3


def setup_bucket(bucket_name: str) -> None:
    s3 = connect_to_s3()
    try:
        s3.create_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' created successfully.")
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


def deploy_react_app(zip_file: Any, session_id: str) -> str:
    s3 = connect_to_s3()
    with zipfile.ZipFile(zip_file, "r") as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            clean_name = name.replace("\\", "/")
            key = f"{session_id}/{clean_name}"
            minetype = mimetypes.guess_type(name)[0] or "application/octet-stream"
            s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=z.read(name), ContentType=minetype, ACL="public-read")
    return f"{ENDPOINT_URL}/{BUCKET_NAME}/{session_id}/dist/index.html"


def deploy_single_html(html_content: str, session_id: str) -> str:
    """Deploy a single HTML string to S3 and return the public URL."""
    s3 = connect_to_s3()
    key = f"published/{session_id}.html"
    s3.put_object(
        Bucket=BUCKET_NAME, Key=key, Body=html_content.encode("utf-8"), ContentType="text/html", ACL="public-read"
    )
    return f"{ENDPOINT_URL}/{BUCKET_NAME}/{key}"
