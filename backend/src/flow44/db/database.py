"""Async database engine and session factory (SQLModel + aiosqlite)."""

from __future__ import annotations

import functools

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import flow44.config


def _get_async_url() -> str:
    """Convert ``sqlite:///path`` to ``sqlite+aiosqlite:///path``."""
    url = flow44.config.settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


@functools.lru_cache
def get_engine(url: str | None = None) -> AsyncEngine:
    """Create (or return cached) async engine."""
    async_url = url or _get_async_url()
    eng = create_async_engine(async_url, echo=False)

    # TODO: this is specific for SQLite, remove when migrating to Postgres
    @event.listens_for(eng.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return eng


@functools.lru_cache
def get_session_factory(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    """Create (or return cached) session factory."""
    return async_sessionmaker(get_engine(url), class_=AsyncSession, expire_on_commit=False)


def async_session() -> AsyncSession:
    """Return a new async session. Tests override this function directly."""
    return get_session_factory()()


async def reset() -> None:
    """Dispose engine and clear caches. Used by tests."""
    if get_engine.cache_info().currsize > 0:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


async def init_db() -> None:
    """Create all tables defined by SQLModel metadata."""
    from sqlmodel import SQLModel  # noqa: PLC0415

    import flow44.db.chat  # noqa: F401, PLC0415
    import flow44.db.events  # noqa: F401, PLC0415
    import flow44.db.project  # noqa: F401, PLC0415

    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
