"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
async def test_db(monkeypatch: pytest.MonkeyPatch):
    """Provide an in-memory SQLite DB with all tables created via SQLModel."""
    # Import model modules to register tables on SQLModel.metadata
    import flow44.db.chat  # noqa: F401
    import flow44.db.events  # noqa: F401
    import flow44.db.project  # noqa: F401

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(test_engine.sync_engine, "connect")
    def _pragma(dbapi_conn, _):  # noqa: ANN001
        dbapi_conn.cursor().execute("PRAGMA foreign_keys=ON")

    test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    monkeypatch.setattr("flow44.db.database.async_session", test_session_factory)

    yield test_session_factory

    await test_engine.dispose()
