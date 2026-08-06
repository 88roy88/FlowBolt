"""Tests for DB helper functions."""

from __future__ import annotations

import pytest

import flow44.config
from flow44.db.database import _get_async_url


class TestDatabaseHelpers:
    def test_get_async_url_uses_asyncpg_driver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(flow44.config.settings, "DB_USER", "user")
        monkeypatch.setattr(flow44.config.settings, "DB_PASSWORD", "pass")
        monkeypatch.setattr(flow44.config.settings, "DB_HOST", "localhost")
        monkeypatch.setattr(flow44.config.settings, "DB_PORT", 5432)
        monkeypatch.setattr(flow44.config.settings, "DB_NAME", "flow44")
        assert _get_async_url() == "postgresql+asyncpg://user:pass@localhost:5432/flow44"
