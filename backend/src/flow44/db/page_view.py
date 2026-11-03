from enum import StrEnum

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Field, SQLModel, select

from flow44.db import database


class PageViewSource(StrEnum):
    preview = "preview"
    production = "production"


class ProjectPageViewCount(SQLModel, table=True):
    """Running view counts per project. Individual views are logged as `page_viewed` BI events."""

    __tablename__ = "project_page_view_counts"

    project_id: str = Field(sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True))
    production_views: int = Field(default=0)
    preview_views: int = Field(default=0)


async def increment_page_views(project_id: str, source: PageViewSource) -> None:
    column = f"{source.value}_views"
    stmt = (
        insert(ProjectPageViewCount)
        .values({"project_id": project_id, column: 1})
        .on_conflict_do_update(index_elements=["project_id"], set_={column: getattr(ProjectPageViewCount, column) + 1})
    )
    async with database.async_session() as session:
        await session.execute(stmt)
        await session.commit()


async def list_page_view_counts() -> dict[str, ProjectPageViewCount]:
    async with database.async_session() as session:
        result = await session.execute(select(ProjectPageViewCount))
        return {row.project_id: row for row in result.scalars().all()}
