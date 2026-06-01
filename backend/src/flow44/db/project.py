import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, select

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
    data_source_id: str = Field(default="")
    data_source_context: str = Field(default="")
    data_sources: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    published_url: str = Field(default="")


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
        query = (
            select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())  # type: ignore[attr-defined]
        )
        result = await session.execute(query)
        return list(result.scalars().all())


async def list_all_projects() -> list[Project]:
    """System-level: returns every project across all users. Never call from a request handler."""
    async with database.async_session() as session:
        query = select(Project).order_by(Project.created_at.desc())  # type: ignore[attr-defined]
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


async def update_project_data_source(project_id: str, data_source_id: str, data_source_context: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.data_source_id = data_source_id
            project.data_source_context = data_source_context
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def update_project_data_sources(project_id: str, data_sources: list[dict[str, Any]]) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.data_sources = data_sources
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def get_project_data_sources(project_id: str) -> list[dict[str, Any]]:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            return []
        if project.data_sources:
            return project.data_sources
        # TODO: what is this VVVVV
        # Fallback: synthesize from single-source columns
        dsid = project.data_source_id
        dsctx = project.data_source_context
        if dsid:
            try:
                ctx = json.loads(dsctx) if dsctx else {}
            except (json.JSONDecodeError, TypeError):
                ctx = {}
            ctx["data_source_id"] = dsid
            return [ctx]
        return []


async def delete_project(project_id: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            await session.delete(project)
            await session.commit()


async def update_project_published_url(project_id: str, url: str) -> None:
    async with database.async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.published_url = url
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()
