import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class UploadKind(StrEnum):
    attachment = "attachment"
    asset = "asset"


class Upload(SQLModel, table=True):
    __tablename__ = "uploads"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(
        sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    kind: UploadKind
    name: str
    s3_key: str
    content_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    created_by: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    deleted_at: str | None = None


def upload_key(project_id: str, upload_id: str) -> str:
    return f"projects/{project_id}/uploads/{upload_id}"


async def save_upload(upload: Upload) -> Upload:
    async with database.async_session() as session:
        session.add(upload)
        await session.commit()
        await session.refresh(upload)
    return upload


async def get_upload(project_id: str, upload_id: str) -> Upload | None:
    async with database.async_session() as session:
        result = await session.execute(
            select(Upload).where(
                Upload.id == upload_id, Upload.project_id == project_id, col(Upload.deleted_at).is_(None)
            )
        )
        return result.scalars().first()


async def get_uploads(project_id: str, upload_ids: list[str]) -> list[Upload]:
    """Return the live uploads among ``upload_ids`` in the given order, skipping unknown ids."""
    if not upload_ids:
        return []
    async with database.async_session() as session:
        result = await session.execute(
            select(Upload).where(
                col(Upload.id).in_(upload_ids), Upload.project_id == project_id, col(Upload.deleted_at).is_(None)
            )
        )
        by_id = {u.id: u for u in result.scalars().all()}
    return [by_id[uid] for uid in upload_ids if uid in by_id]
