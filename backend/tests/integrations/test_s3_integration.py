from unittest.mock import MagicMock, patch

import pytest

from flow44.config import settings
from flow44.integrations.s3 import connect_to_s3, deploy_single_html, setup_bucket


@pytest.fixture(autouse=True)
def clear_lru_cache():
    connect_to_s3.cache_clear()
    yield
    connect_to_s3.cache_clear()


def test_connect_to_s3_is_singleton():
    with patch("boto3.client") as mock_boto_client:
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        c1 = connect_to_s3()
        c2 = connect_to_s3()

        assert c1 is c2
        assert mock_boto_client.call_count == 1


def test_setup_bucket():
    with patch("flow44.integrations.s3.connect_to_s3") as mock_connect:
        mock_client = MagicMock()
        mock_connect.return_value = mock_client

        bucket_name = "test-bucket"
        setup_bucket(bucket_name)

        mock_client.create_bucket.assert_called_once_with(Bucket=bucket_name)
        mock_client.put_bucket_policy.assert_called_once()
        args, kwargs = mock_client.put_bucket_policy.call_args
        assert kwargs["Bucket"] == bucket_name
        assert "Statement" in kwargs["Policy"]


def test_deploy_single_html():
    with patch("flow44.integrations.s3.connect_to_s3") as mock_connect:
        mock_client = MagicMock()
        mock_connect.return_value = mock_client

        html_content = "<html>test</html>"
        project_id = "proj-123"

        # Ensure settings are controlled
        with patch.object(settings, "S3_BUCKET_NAME", "my-bucket"):
            with patch.object(settings, "S3_ENDPOINT_URL", "http://s3.local"):
                url = deploy_single_html(html_content, project_id)

                expected_key = f"published/{project_id}.html"
                mock_client.put_object.assert_called_once_with(
                    Bucket="my-bucket",
                    Key=expected_key,
                    Body=html_content.encode("utf-8"),
                    ContentType="text/html",
                    ACL="public-read",
                    StorageClass=settings.S3_STORAGE_CLASS,
                )
                assert url == f"http://s3.local/my-bucket/{expected_key}"
