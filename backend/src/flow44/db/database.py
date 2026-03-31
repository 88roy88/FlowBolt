import functools
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

import flow44.config


def build_db_url(config: flow44.config.Settings, async_db: bool) -> str:
    """Builds a database URL string from components, supporting both SQLite and Postgres."""
    if config.DB_SCHEME == "sqlite":
        # SQLite: use aiosqlite for async, standard sqlite driver otherwise
        adapter = "sqlite+aiosqlite" if async_db else "sqlite"
        return f"{adapter}:///{config.DB_NAME}"

    # Postgres: use asyncpg (we only use async connections)
    db_adapter = "postgresql+asyncpg" if async_db else "postgresql"
    url = f"{db_adapter}://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}"
    if config.DB_NAME:
        url += f"/{config.DB_NAME}"
    return url


def _get_async_url() -> str:
    """Provides the asynchronous database connection string for engines."""
    return build_db_url(flow44.config.settings, async_db=True)


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

    # Enable foreign keys for SQLite (SQLite-specific pragma)
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
    # Ping the engine to ensure connectivity
    async with get_engine().begin() as conn:
        await conn.execute(text("SELECT 1"))
