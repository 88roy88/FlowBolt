from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from flow44.db import database


class PausedTurn(SQLModel, table=True):
    __tablename__ = "paused_turns"

    project_id: str = Field(primary_key=True)
    phase: str
    state_json: str = Field(default="")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def pause_turn(project_id: str, phase: str, state_json: str) -> None:
    async with database.async_session() as session:
        await session.merge(PausedTurn(project_id=project_id, phase=phase, state_json=state_json))
        await session.commit()


async def get_paused_turn(project_id: str) -> PausedTurn | None:
    async with database.async_session() as session:
        return await session.get(PausedTurn, project_id)


async def clear_paused_turn(project_id: str) -> None:
    async with database.async_session() as session:
        existing = await session.get(PausedTurn, project_id)
        if existing:
            await session.delete(existing)
            await session.commit()
