import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel, col, select

from flow44.ai.state import DataSourceContext
from flow44.db import database


class ProjectDataSource(SQLModel, table=True):
    __tablename__ = "project_data_sources"
    __table_args__ = (UniqueConstraint("project_id", "data_source_id", name="uq_project_data_source"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(index=True)
    type: str = Field(default="flow_package")
    data_source_id: str
    data_source_name: str = Field(default="")
    sanitized_name: str = Field(default="")
    queries: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    params_info: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    can_run_without_input: bool = Field(default=False)
    data_schema: str = Field(default="")
    relevant_fields: str = Field(default="")
    data_characteristics: str = Field(default="")
    integration_notes: str = Field(default="")
    param_ux_hints: str = Field(default="")


def _row_to_context(row: ProjectDataSource) -> DataSourceContext:
    return DataSourceContext(
        type=row.type,
        data_source_id=row.data_source_id,
        data_source_name=row.data_source_name,
        sanitized_name=row.sanitized_name,
        queries=row.queries,
        params_info=row.params_info,
        can_run_without_input=row.can_run_without_input,
        data_schema=row.data_schema,
        relevant_fields=row.relevant_fields,
        data_characteristics=row.data_characteristics,
        integration_notes=row.integration_notes,
        param_ux_hints=row.param_ux_hints,
    )


async def get_project_data_sources(project_id: str) -> list[DataSourceContext]:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectDataSource)
            .where(col(ProjectDataSource.project_id) == project_id)
            .order_by(col(ProjectDataSource.data_source_id))
        )
        return [_row_to_context(row) for row in result.scalars().all()]


async def update_project_data_sources(project_id: str, data_sources: Sequence[DataSourceContext]) -> None:
    """Replace all data sources for a project. Caller is responsible for merging with existing."""
    async with database.async_session() as session:
        existing = await session.execute(
            select(ProjectDataSource).where(col(ProjectDataSource.project_id) == project_id)
        )
        by_id = {row.data_source_id: row for row in existing.scalars().all()}

        for ctx in data_sources:
            row = by_id.get(ctx["data_source_id"])
            if row is None:
                row = ProjectDataSource(project_id=project_id, data_source_id=ctx["data_source_id"])
                session.add(row)
            row.type = ctx.get("type", "flow_package")
            row.data_source_name = ctx["data_source_name"]
            row.sanitized_name = ctx["sanitized_name"]
            row.queries = ctx["queries"]
            row.params_info = ctx["params_info"]
            row.can_run_without_input = ctx["can_run_without_input"]
            row.data_schema = ctx["data_schema"]
            row.relevant_fields = ctx["relevant_fields"]
            row.data_characteristics = ctx["data_characteristics"]
            row.integration_notes = ctx["integration_notes"]
            row.param_ux_hints = ctx.get("param_ux_hints", "")

        await session.commit()
