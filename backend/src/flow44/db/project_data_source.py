import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class DataSourceBase(SQLModel):
    project_id: str = ""
    type: str = "flow_package"
    data_source_id: str = ""
    data_source_name: str = ""
    sanitized_name: str = ""
    queries: list[dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    params_info: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    can_run_without_input: bool = False
    data_schema: str = ""
    relevant_fields: str = ""
    data_characteristics: str = ""
    integration_notes: str = ""
    param_ux_hints: str = ""


class ProjectDataSource(DataSourceBase, table=True):
    __tablename__ = "project_data_sources"
    __table_args__ = (UniqueConstraint("project_id", "type", "data_source_id", name="uq_project_data_source"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(default="", index=True)


class DataSourceContext(DataSourceBase):
    """In-memory representation of a data source, including transient fields not stored to the DB."""

    id: str = ""
    sample_data: dict[str, Any] | None = None
    module_path: str = ""
    generated_files: dict[str, str] = Field(default_factory=dict)

    def to_prompt_context(self) -> dict[str, Any]:
        """Return this data source for prompt templates, with sample data truncated."""
        return {
            **self.model_dump(),
            "sample_data_json": (
                json.dumps(self.sample_data, indent=2)[:1000] if self.sample_data is not None else None
            ),
        }


def _row_to_context(row: ProjectDataSource) -> DataSourceContext:
    return DataSourceContext(**row.model_dump())


async def get_project_data_sources(project_id: str) -> list[DataSourceContext]:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectDataSource)
            .where(col(ProjectDataSource.project_id) == project_id)
            .order_by(col(ProjectDataSource.data_source_id))
        )
        return [_row_to_context(row) for row in result.scalars().all()]


async def update_project_data_sources(project_id: str, data_sources: Sequence[DataSourceContext]) -> None:
    """Upsert data sources for a project. Caller is responsible for merging with existing if needed."""
    async with database.async_session() as session:
        existing = await session.execute(
            select(ProjectDataSource).where(col(ProjectDataSource.project_id) == project_id)
        )
        by_id = {(row.type, row.data_source_id): row for row in existing.scalars().all()}

        _transient = {"id", "project_id", "sample_data", "module_path", "generated_files"}
        for ctx in data_sources:
            persistent = ctx.model_dump(exclude=_transient)
            row = by_id.get((ctx.type, ctx.data_source_id))
            if row is None:
                session.add(ProjectDataSource(project_id=project_id, **persistent))
            else:
                for k, v in persistent.items():
                    setattr(row, k, v)

        await session.commit()
