import functools
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import flow44.config


def _get_async_url() -> str:
    url = flow44.config.settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@functools.lru_cache
def get_engine(url: str | None = None) -> AsyncEngine:
    async_url = url or _get_async_url()

    kwargs = {}
    if not async_url.startswith("sqlite"):
        kwargs.update(
            {
                "pool_size": flow44.config.settings.DB_POOL_SIZE,
                "max_overflow": flow44.config.settings.DB_MAX_OVERFLOW,
                "pool_recycle": flow44.config.settings.DB_POOL_RECYCLE,
                "pool_pre_ping": flow44.config.settings.DB_POOL_PRE_PING,
            }
        )

    eng = create_async_engine(async_url, echo=False, **kwargs)

    # TODO: this is specific for SQLite, remove when migrating to Postgres
    @event.listens_for(eng.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_conn: Any, _connection_record: Any) -> None:
        if eng.dialect.name == "sqlite":
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return eng


@functools.lru_cache
def get_session_factory(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(url), class_=AsyncSession, expire_on_commit=False)


def async_session() -> AsyncSession:
    return get_session_factory()()


async def reset() -> None:
    if get_engine.cache_info().currsize > 0:
        await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


async def init_db() -> None:
    """Initialize database connection. Metadata creation is now handled by Alembic."""
    # We just ping the engine to ensure connectivity
    async with get_engine().begin() as conn:
        await conn.execute(text("SELECT 1"))
