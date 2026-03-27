"""Transient storage for build plans awaiting user approval."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, select

from flow44.db import database


class PendingPlan(SQLModel, table=True):
    __tablename__ = "pending_plans"

    project_id: str = Field(primary_key=True)
    state_json: str = Field(default="")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def save_pending_plan(project_id: str, state_json: str) -> None:
    async with database.async_session() as session:
        existing = await session.get(PendingPlan, project_id)
        if existing:
            existing.state_json = state_json
            existing.created_at = datetime.now(UTC).isoformat()
        else:
            session.add(PendingPlan(project_id=project_id, state_json=state_json))
        await session.commit()


async def get_pending_plan(project_id: str) -> str | None:
    async with database.async_session() as session:
        result = await session.execute(select(PendingPlan).where(PendingPlan.project_id == project_id))
        row = result.scalar_one_or_none()
        return row.state_json if row else None


async def delete_pending_plan(project_id: str) -> None:
    async with database.async_session() as session:
        existing = await session.get(PendingPlan, project_id)
        if existing:
            await session.delete(existing)
            await session.commit()
