from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class PageViewSource(StrEnum):
    preview = "preview"
    production = "production"


class ProjectViewCount(SQLModel, table=True):
    __tablename__ = "project_view_counts"

    project_id: str = Field(sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True))
    production_views: int = Field(default=0)
    preview_views: int = Field(default=0)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


async def increment_page_views(project_id: str, source: PageViewSource) -> None:
    column = f"{source.value}_views"
    stmt = (
        insert(ProjectViewCount)
        .values({"project_id": project_id, column: 1})
        .on_conflict_do_update(index_elements=["project_id"], set_={column: getattr(ProjectViewCount, column) + 1})
    )
    async with database.async_session() as session:
        await session.execute(stmt)
        await session.commit()


async def list_page_view_counts(project_ids: list[str]) -> dict[str, ProjectViewCount]:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectViewCount).where(col(ProjectViewCount.project_id).in_(project_ids))
        )
        return {row.project_id: row for row in result.scalars().all()}
