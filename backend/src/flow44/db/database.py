"""Async database engine and session factory (SQLModel + aiosqlite)."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flow44.config import settings


def _get_async_url() -> str:
    """Convert ``sqlite:///path`` to ``sqlite+aiosqlite:///path``."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


engine = create_async_engine(_get_async_url(), echo=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_foreign_keys(dbapi_conn, _connection_record):  # noqa: ANN001
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables defined by SQLModel metadata."""
    from sqlmodel import SQLModel  # noqa: PLC0415

    # Import model modules so their tables are registered on SQLModel.metadata
    import flow44.db.chat  # noqa: F401, PLC0415
    import flow44.db.events  # noqa: F401, PLC0415
    import flow44.db.project  # noqa: F401, PLC0415

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
