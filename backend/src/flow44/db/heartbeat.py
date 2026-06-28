import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, String, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Field, SQLModel, col

from flow44.config import settings
from flow44.db import database
from flow44.db.events import emit_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Heartbeat model
# ---------------------------------------------------------------------------


class AgentRunHeartbeat(SQLModel, table=True):
    __tablename__ = "agent_run_heartbeat"

    project_id: str = Field(sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True))
    beat_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    )


def _insert() -> Any:
    """The dialect-native INSERT that supports ON CONFLICT (upsert)."""
    return pg_insert if database.get_engine().dialect.name == "postgresql" else sqlite_insert


# ---------------------------------------------------------------------------
# Heartbeat writes — atomic upserts (the heartbeat row is also the run-lock)
# ---------------------------------------------------------------------------


async def touch_heartbeat(project_id: str) -> None:
    """Refresh this project's heartbeat (one row per project)."""
    now = datetime.now(UTC)
    stmt = (
        _insert()(AgentRunHeartbeat)
        .values(project_id=project_id, beat_at=now)
        .on_conflict_do_update(index_elements=["project_id"], set_={"beat_at": now})
    )
    async with database.async_session() as session:
        await session.execute(stmt)
        await session.commit()


async def try_claim_run(project_id: str) -> bool:
    """Atomically claim the run-lock for this project.

    Returns True if claimed — no heartbeat existed, or the existing one was stale.
    Returns False if a fresh heartbeat already holds the lock (a run is active).
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=settings.AGENT_RUN_STALE_TIMEOUT)
    beat_at = col(AgentRunHeartbeat.beat_at)
    stmt = (
        _insert()(AgentRunHeartbeat)
        .values(project_id=project_id, beat_at=now)
        .on_conflict_do_update(
            index_elements=["project_id"],
            set_={"beat_at": now},
            where=(beat_at < cutoff) | beat_at.is_(None),
        )
        .returning(col(AgentRunHeartbeat.project_id))
    )
    async with database.async_session() as session:
        result = await session.execute(stmt)
        await session.commit()
        return result.first() is not None


async def get_heartbeat(project_id: str) -> AgentRunHeartbeat | None:
    async with database.async_session() as session:
        return await session.get(AgentRunHeartbeat, project_id)


async def clear_heartbeat(project_id: str) -> None:
    async with database.async_session() as session:
        hb = await session.get(AgentRunHeartbeat, project_id)
        if hb is not None:
            await session.delete(hb)
            await session.commit()


# ---------------------------------------------------------------------------
# Liveness — a run is alive iff its heartbeat is still fresh
# ---------------------------------------------------------------------------


def _is_fresh(ts: datetime | None, window_seconds: int) -> bool:
    """True if the timestamp is within the given window (SQLite stamps are naive UTC)."""
    if ts is None:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts > datetime.now(UTC) - timedelta(seconds=window_seconds)


async def is_run_active(project_id: str) -> bool:
    hb = await get_heartbeat(project_id)
    return hb is not None and _is_fresh(hb.beat_at, settings.AGENT_RUN_STALE_TIMEOUT)


async def reap_stale_runs() -> int:
    """Close every run whose heartbeat has gone stale.

    Atomically deletes stale heartbeats (so a run refreshed mid-sweep is left alone,
    and concurrent sweeps each reap a row at most once), then appends a terminal
    'error' event per reaped run so the UI unsticks.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.AGENT_RUN_STALE_TIMEOUT)
    beat_at = col(AgentRunHeartbeat.beat_at)
    async with database.async_session() as session:
        result = await session.execute(
            delete(AgentRunHeartbeat)
            .where((beat_at < cutoff) | beat_at.is_(None))
            .returning(col(AgentRunHeartbeat.project_id))
        )
        stale_ids = list(result.scalars().all())
        await session.commit()

    for project_id in stale_ids:
        try:
            await emit_event(project_id, {"type": "error", "message": "Agent run was interrupted"})
        except Exception:
            logger.exception("[heartbeat] Failed to emit interruption for %s", project_id)

    if stale_ids:
        logger.info("[heartbeat] Reaped %d stale run(s)", len(stale_ids))
    return len(stale_ids)
