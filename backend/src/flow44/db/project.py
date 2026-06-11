import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, col, select

from flow44.ai.state import DataSourceContext
from flow44.db import database


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    summary: str = Field(default="")
    selected_model: str = Field(default="")
    data_sources: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    published_url: str | None = Field(default=None, sa_column_kwargs={"unique": True})
    published_at: str | None = Field(default=None)


async def create_project(name: str, user_id: str) -> Project:
    project = Project(name=name, user_id=user_id)
    async with database.async_session() as session:
        session.add(project)
        await session.commit()
        await session.refresh(project)
    return project


async def get_project(project_id: str) -> Project | None:
    async with database.async_session() as session:
        return await session.get(Project, project_id)


async def list_user_projects(user_id: str) -> list[Project]:
    async with database.async_session() as session:
        query = select(Project).where(Project.user_id == user_id).order_by(col(Project.created_at).desc())
        result = await session.execute(query)
        return list(result.scalars().all())


async def list_all_projects() -> list[Project]:
    """System-level: returns every project across all users. Never call from a request handler."""
    async with database.async_session() as session:
        query = select(Project).order_by(col(Project.created_at).desc())
        result = await session.execute(query)
        return list(result.scalars().all())


async def update_project_summary(project_id: str, summary: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.summary = summary
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def rename_project(project_id: str, name: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.name = name
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def update_project_model(project_id: str, model: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.selected_model = model
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


_TRANSIENT_KEYS = {"sample_data", "generated_files"}


async def update_project_data_sources(project_id: str, data_sources: Sequence[DataSourceContext]) -> None:
    stored = [{k: v for k, v in ds.items() if k not in _TRANSIENT_KEYS} for ds in data_sources]
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.data_sources = stored
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def get_project_data_sources(project_id: str) -> list[dict[str, Any]]:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            return []
        return project.data_sources or []


async def delete_project(project_id: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            await session.delete(project)
            await session.commit()


async def get_project_by_handle(handle: str) -> Project | None:
    async with database.async_session() as session:
        result = await session.execute(select(Project).where(Project.published_url == handle))
        return result.scalar_one_or_none()


async def is_handle_taken(handle: str, exclude_project_id: str) -> bool:
    async with database.async_session() as session:
        result = await session.execute(
            select(Project).where(Project.published_url == handle, Project.id != exclude_project_id)
        )
        return result.scalar_one_or_none() is not None


async def update_project_published_url(project_id: str, handle: str) -> None:
    """Set the project's handle. Caller must ensure the project exists."""
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if not project:
            raise Exception("project not found")  # noqa: TRY002
        now = datetime.now(UTC).isoformat()
        project.published_url = handle
        project.published_at = now
        project.updated_at = now
        session.add(project)
        await session.commit()
