import json
import mimetypes
import boto3
import os
import zipfile
import io
import botocore.exceptions as ClientError
from dotenv import load_dotenv


load_dotenv()

ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL')
ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
SECRET_KEY = os.getenv('S3_SECRET_KEY')
BUCKET_NAME = os.getenv('S3_BUCKET_NAME')


def connect_to_s3():
    s3 = boto3.client(
        "s3",
        use_ssl= ENDPOINT_URL.startswith("https://"),
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        endpoint_url=ENDPOINT_URL,
    )
    return s3


def setup_bucket(bucket_name):
    s3 = connect_to_s3()
    try:
        s3.create_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' created successfully.")
    except ClientError as e:
        if e.response['Error']['Code'] not in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
            raise
    s3.put_bucket_policy(
        Bucket=bucket_name,
        Policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                }
            ]})
    )


def deploy_react_app(zip_file, session_id):
    s3 = connect_to_s3()
    with zipfile.ZipFile(zip_file, "r") as z:
        for name in z.namelist():
            if name.endswith('/'):
                continue
            clean_name = name.replace("\\", "/")
            key = f"{session_id}/{clean_name}"
            minetype = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=z.read(name), ContentType=minetype, ACL='public-read')
    return f"{ENDPOINT_URL}/{BUCKET_NAME}/{session_id}/dist/index.html"


def get_zip_from_path(file_path):
    with open(file_path, 'rb') as f:
        zip_buffer = io.BytesIO(f.read())
    return zip_buffer


def clear_bucket():
    s3 = connect_to_s3()
    try:
        content = s3.list_objects_v2(Bucket=BUCKET_NAME).get('Contents', [])
        if content:
            s3.delete_objects(
                Bucket=BUCKET_NAME,
                Delete={'Objects': [{'Key': obj['Key']} for obj in content], 'Quiet': True}
            )
    except ClientError:
        pass


# if __name__ == "__main__":
    # setup_bucket(BUCKET_NAME)
    # clear_bucket()
    # zip_file = get_zip_from_path("./integrations/testbundle.zip")
    # url = deploy_react_app(zip_file, "test-session2")
    # print(f"App deployed at: {url}")