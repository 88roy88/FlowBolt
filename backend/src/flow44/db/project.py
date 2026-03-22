"""Project model and CRUD operations."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel, select

from flow44.db.database import async_session


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    summary: str = Field(default="")
    selected_model: str = Field(default="")
    data_source_id: str = Field(default="")
    data_source_context: str = Field(default="", sa_column=Column(Text, default=""))
    data_sources: str = Field(default="[]", sa_column=Column(Text, default="[]"))


async def create_project(name: str) -> Project:
    """Insert a new project and return it."""
    project = Project(name=name)
    async with async_session() as session:
        session.add(project)
        await session.commit()
        await session.refresh(project)
    return project


async def get_project(project_id: str) -> Project | None:
    """Fetch a single project by id."""
    async with async_session() as session:
        return await session.get(Project, project_id)


async def list_projects() -> list[Project]:
    """Return all projects ordered by creation date (newest first)."""
    async with async_session() as session:
        result = await session.execute(select(Project).order_by(Project.created_at.desc()))  # type: ignore[arg-type]
        return list(result.scalars().all())


async def update_project_summary(project_id: str, summary: str) -> None:
    """Update the summary field for a project."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.summary = summary
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def rename_project(project_id: str, name: str) -> None:
    """Update the name of a project."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.name = name
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def update_project_model(project_id: str, model: str) -> None:
    """Update the selected_model field for a project."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.selected_model = model
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def update_project_data_source(project_id: str, data_source_id: str, data_source_context: str) -> None:
    """Update the data_source_id and data_source_context fields for a project."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.data_source_id = data_source_id
            project.data_source_context = data_source_context
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def update_project_data_sources(project_id: str, data_sources: list[dict[str, Any]]) -> None:
    """Update the data_sources column (JSON array) for a project."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            project.data_sources = json.dumps(data_sources)
            project.updated_at = datetime.now(UTC).isoformat()
            session.add(project)
            await session.commit()


async def get_project_data_sources(project_id: str) -> list[dict[str, Any]]:
    """Read the data_sources column, falling back to single data_source_id/data_source_context."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project is None:
            return []
        raw = project.data_sources
        if raw and raw != "[]":
            try:
                return cast(list[dict[str, Any]], json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass
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
    """Delete a project and its chat messages (cascade)."""
    async with async_session() as session:
        project = await session.get(Project, project_id)
        if project:
            await session.delete(project)
            await session.commit()
