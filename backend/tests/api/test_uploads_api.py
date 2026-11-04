from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.api.deps import get_project
from flow44.config import settings
from flow44.db.uploads import Upload, UploadKind
from flow44.main import app

client = TestClient(app)

PROJECT_ID = "proj-uploads"


@pytest.fixture
def storage() -> Iterator[MagicMock]:
    project = MagicMock()
    project.id = PROJECT_ID
    stored: dict[str, Any] = {}

    async def upload_stream(key: str, chunks: AsyncIterator[bytes], content_type: str) -> int:
        stored["key"] = key
        stored["body"] = b"".join([c async for c in chunks])
        return len(stored["body"])

    s3 = MagicMock()
    s3.upload_stream = AsyncMock(side_effect=upload_stream)
    s3.stored = stored
    app.dependency_overrides[get_project] = lambda: project
    with (
        patch("flow44.api.uploads.s3_storage", s3),
        patch("flow44.api.uploads.save_upload", AsyncMock(side_effect=lambda u: u)),
    ):
        yield s3
    app.dependency_overrides.pop(get_project, None)


def _post(content: bytes, name: str, content_type: str, **params: Any) -> Any:
    return client.post(
        f"/api/uploads/{PROJECT_ID}/attachments",
        params={"name": name, **params},
        content=content,
        headers={"Content-Type": content_type},
    )


def test_attachment_upload_streams_to_its_own_key(storage: MagicMock) -> None:
    response = _post(b"\x89PNG", "shot.png", "image/png", width=800, height=600)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "shot.png"
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == 4
    assert (body["width"], body["height"]) == (800, 600)
    assert storage.stored["key"] == f"projects/{PROJECT_ID}/uploads/{body['id']}"
    assert storage.stored["body"] == b"\x89PNG"


def test_path_parts_are_stripped_from_the_name(storage: MagicMock) -> None:
    assert _post(b"x", "C:\\Users\\me\\notes.txt", "text/plain").json()["name"] == "notes.txt"


def test_content_type_falls_back_to_the_extension(storage: MagicMock) -> None:
    assert _post(b"a,b", "data.csv", "application/octet-stream").json()["content_type"] == "text/csv"


@pytest.mark.parametrize(("name", "content_type"), [("page.html", "text/html"), ("logo.svg", "image/svg+xml")])
def test_types_that_could_run_script_are_refused(storage: MagicMock, name: str, content_type: str) -> None:
    assert _post(b"<script>", name, content_type).status_code == 415
    storage.upload_stream.assert_not_awaited()


def test_oversized_attachment_is_refused(storage: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "UPLOAD_MAX_ATTACHMENT_BYTES", 3)

    assert _post(b"\x89PNG", "shot.png", "image/png").status_code == 413


def test_content_is_served_with_its_type_and_no_sniffing() -> None:
    upload = Upload(
        project_id=PROJECT_ID,
        kind=UploadKind.attachment,
        name="shot.png",
        s3_key="k",
        content_type="image/png",
        size_bytes=4,
        created_by="u",
    )
    project = MagicMock()
    project.id = PROJECT_ID
    s3 = MagicMock()
    s3.read_upload = AsyncMock(return_value=b"\x89PNG")
    app.dependency_overrides[get_project] = lambda: project
    try:
        with (
            patch("flow44.api.uploads.s3_storage", s3),
            patch("flow44.api.uploads.get_upload", AsyncMock(return_value=upload)),
        ):
            response = client.get(f"/api/uploads/{PROJECT_ID}/{upload.id}/content")
        with patch("flow44.api.uploads.get_upload", AsyncMock(return_value=None)):
            missing = client.get(f"/api/uploads/{PROJECT_ID}/nope/content")
    finally:
        app.dependency_overrides.pop(get_project, None)

    assert response.status_code == 200
    assert response.content == b"\x89PNG"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    s3.read_upload.assert_awaited_once_with("k")
    assert missing.status_code == 404
