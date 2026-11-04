from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from flow44.db.project import create_project
from flow44.db.uploads import Upload, UploadKind, get_upload, get_uploads, save_upload, upload_key


async def _attachment(project_id: str, name: str, *, deleted: bool = False) -> Upload:
    upload = Upload(
        project_id=project_id,
        kind=UploadKind.attachment,
        name=name,
        s3_key="",
        content_type="image/png",
        size_bytes=3,
        created_by="test-user",
        deleted_at=datetime.now(UTC).isoformat() if deleted else None,
    )
    upload.s3_key = upload_key(project_id, upload.id)
    return await save_upload(upload)


@pytest.mark.asyncio
async def test_get_uploads_keeps_request_order_and_skips_other_projects_and_deleted(test_db) -> None:
    mine = await create_project("Mine", user_id="test-user")
    other = await create_project("Other", user_id="test-user")
    a = await _attachment(mine.id, "a.png")
    b = await _attachment(mine.id, "b.png")
    foreign = await _attachment(other.id, "c.png")
    gone = await _attachment(mine.id, "d.png", deleted=True)

    found = await get_uploads(mine.id, [b.id, foreign.id, gone.id, "missing", a.id])

    assert [u.name for u in found] == ["b.png", "a.png"]


@pytest.mark.asyncio
async def test_get_upload_is_scoped_to_the_project(test_db) -> None:
    mine = await create_project("Mine", user_id="test-user")
    other = await create_project("Other", user_id="test-user")
    a = await _attachment(mine.id, "a.png")

    assert (await get_upload(mine.id, a.id)) is not None
    assert await get_upload(other.id, a.id) is None
    assert a.s3_key == f"projects/{mine.id}/uploads/{a.id}"


async def _asset(project_id: str, name: str, *, deleted: bool = False) -> Upload:
    upload = Upload(
        project_id=project_id,
        kind=UploadKind.asset,
        name=name,
        s3_key="k",
        content_type="image/png",
        size_bytes=3,
        created_by="test-user",
        deleted_at=datetime.now(UTC).isoformat() if deleted else None,
    )
    return await save_upload(upload)


@pytest.mark.asyncio
async def test_live_asset_names_are_unique_per_project(test_db) -> None:
    mine = await create_project("Mine", user_id="test-user")
    await _asset(mine.id, "logo.png")

    with pytest.raises(IntegrityError):
        await _asset(mine.id, "logo.png")


@pytest.mark.asyncio
async def test_asset_name_uniqueness_skips_attachments_deleted_assets_and_other_projects(test_db) -> None:
    mine = await create_project("Mine", user_id="test-user")
    other = await create_project("Other", user_id="test-user")
    await _asset(mine.id, "logo.png", deleted=True)
    await _asset(mine.id, "logo.png")
    await _asset(other.id, "logo.png")
    await _attachment(mine.id, "logo.png")
    await _attachment(mine.id, "logo.png")
