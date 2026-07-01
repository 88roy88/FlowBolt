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
    beat_at: datetime = Field(sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))


def _insert() -> Any:
    """The dialect-native INSERT that supports ON CONFLICT (upsert)."""
    return pg_insert if database.get_engine().dialect.name == "postgresql" else sqlite_insert


def _stale_cutoff() -> datetime:
    return datetime.now(UTC) - timedelta(seconds=settings.AGENT_RUN_STALE_TIMEOUT)


def _stale() -> Any:
    """WHERE clause matching heartbeats older than the stale cutoff."""
    return col(AgentRunHeartbeat.beat_at) < _stale_cutoff()


async def _commit(stmt: Any) -> Any:
    async with database.async_session() as session:
        result = await session.execute(stmt)
        await session.commit()
        return result


# ---------------------------------------------------------------------------
# Heartbeat writes — atomic upserts (the heartbeat row is also the run-lock)
# ---------------------------------------------------------------------------


async def touch_heartbeat(project_id: str) -> datetime:
    """Refresh this project's heartbeat (one row per project); return the beat written."""
    now = datetime.now(UTC)
    await _commit(
        _insert()(AgentRunHeartbeat)
        .values(project_id=project_id, beat_at=now)
        .on_conflict_do_update(index_elements=["project_id"], set_={"beat_at": now})
    )
    return now


async def try_claim_run(project_id: str) -> datetime | None:
    """Atomically claim the run-lock.

    Returns the claimed beat (the lock token) on success, or None when a fresh
    heartbeat already holds it.
    """
    now = datetime.now(UTC)
    stmt = (
        _insert()(AgentRunHeartbeat)
        .values(project_id=project_id, beat_at=now)
        .on_conflict_do_update(index_elements=["project_id"], set_={"beat_at": now}, where=_stale())
        .returning(col(AgentRunHeartbeat.project_id))
    )
    return now if (await _commit(stmt)).first() is not None else None


async def get_heartbeat(project_id: str) -> AgentRunHeartbeat | None:
    async with database.async_session() as session:
        return await session.get(AgentRunHeartbeat, project_id)


async def clear_heartbeat(project_id: str, *, only_beat: datetime | None = None) -> None:
    """Release this project's run-lock.

    With only_beat set, delete only while it is still our beat, so a lock a newer run
    has since claimed (after ours was reaped) is never cleared out from under it.
    """
    stmt = delete(AgentRunHeartbeat).where(col(AgentRunHeartbeat.project_id) == project_id)
    if only_beat is not None:
        stmt = stmt.where(col(AgentRunHeartbeat.beat_at) == only_beat)
    await _commit(stmt)


# ---------------------------------------------------------------------------
# Liveness — a run is alive iff its heartbeat is still fresh
# ---------------------------------------------------------------------------


def _is_fresh(ts: datetime, window_seconds: int) -> bool:
    """True if the timestamp is within the given window (SQLite stamps are naive UTC)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts > datetime.now(UTC) - timedelta(seconds=window_seconds)


async def is_run_active(project_id: str) -> bool:
    hb = await get_heartbeat(project_id)
    return hb is not None and _is_fresh(hb.beat_at, settings.AGENT_RUN_STALE_TIMEOUT)


async def reap_stale_runs() -> int:
    """Atomically delete stale heartbeats and emit a terminal 'error' event per reaped run.

    Atomic delete means a run refreshed mid-sweep is left alone and concurrent sweeps
    each reap a row at most once.
    """
    result = await _commit(delete(AgentRunHeartbeat).where(_stale()).returning(col(AgentRunHeartbeat.project_id)))
    stale_ids = list(result.scalars().all())

    for project_id in stale_ids:
        try:
            await emit_event(project_id, {"type": "phase", "phase": "idle"})
            await emit_event(project_id, {"type": "error", "message": "Agent run was interrupted"})
        except Exception:
            logger.exception("[heartbeat] Failed to emit interruption for %s", project_id)

    if stale_ids:
        logger.info("[heartbeat] Reaped %d stale run(s)", len(stale_ids))
    return len(stale_ids)
