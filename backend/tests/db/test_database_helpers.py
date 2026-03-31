"""Tests for DB helper functions."""

from __future__ import annotations

import pytest

import flow44.config
from flow44.db.database import _get_async_url, get_engine


class TestDatabaseHelpers:
    def test_get_async_url_converts_sqlite_to_async_driver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(flow44.config.settings, "DB_SCHEME", "sqlite")
        monkeypatch.setattr(flow44.config.settings, "DB_NAME", "tmp/flowbolt.db")
        assert _get_async_url() == "sqlite+aiosqlite:///tmp/flowbolt.db"

    async def test_get_engine_sets_sqlite_foreign_keys_pragma(self) -> None:
        engine = get_engine("sqlite+aiosqlite:///:memory:")
        async with engine.connect() as conn:
            result = await conn.exec_driver_sql("PRAGMA foreign_keys")
            assert result.scalar_one() == 1
        await engine.dispose()
