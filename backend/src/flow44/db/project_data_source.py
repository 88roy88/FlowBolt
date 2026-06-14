import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class ProjectDataSource(SQLModel, table=True):
    __tablename__ = "project_data_sources"
    __table_args__ = (UniqueConstraint("project_id", "type", "data_source_id", name="uq_project_data_source"),)

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

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def items(self) -> Any:
        return self.model_dump().items()


class DataSourceContext(ProjectDataSource):
    """In-memory context — extends ProjectDataSource with transient fields not stored to the DB."""

    id: str = Field(default="")  # type: ignore[assignment]
    project_id: str = Field(default="")  # type: ignore[assignment]
    sample_data: dict[str, Any] | None = None
    module_path: str = ""
    generated_files: dict[str, str] = Field(default_factory=dict)


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
