"""Tests for build_db_url function."""

from flow44.config import Settings
from flow44.db.database import build_db_url

# ruff: noqa: S106  # Test fixtures may use hardcoded passwords


class TestBuildDbUrlSQLite:
    def test_sqlite_async(self) -> None:
        config = Settings(
            DB_SCHEME="sqlite",
            DB_NAME="test.db",
            DB_USER="",
            DB_PASSWORD="",
            DB_HOST="",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=True)
        assert result == "sqlite+aiosqlite:///test.db"

    def test_sqlite_sync(self) -> None:
        config = Settings(
            DB_SCHEME="sqlite",
            DB_NAME="test.db",
            DB_USER="",
            DB_PASSWORD="",
            DB_HOST="",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=False)
        assert result == "sqlite:///test.db"

    def test_sqlite_memory(self) -> None:
        config = Settings(
            DB_SCHEME="sqlite",
            DB_NAME=":memory:",
            DB_USER="",
            DB_PASSWORD="",
            DB_HOST="",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=True)
        assert result == "sqlite+aiosqlite:///:memory:"

    def test_sqlite_relative_path(self) -> None:
        config = Settings(
            DB_SCHEME="sqlite",
            DB_NAME="./data/test.db",
            DB_USER="",
            DB_PASSWORD="",
            DB_HOST="",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=True)
        assert result == "sqlite+aiosqlite:///./data/test.db"


class TestBuildDbUrlPostgres:
    def test_postgres_async_with_db_name(self) -> None:
        config = Settings(
            DB_SCHEME="postgresql",
            DB_NAME="testdb",
            DB_USER="user",
            DB_PASSWORD="pass",
            DB_HOST="localhost",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=True)
        assert result == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

    def test_postgres_sync_with_db_name(self) -> None:
        config = Settings(
            DB_SCHEME="postgresql",
            DB_NAME="testdb",
            DB_USER="user",
            DB_PASSWORD="pass",
            DB_HOST="localhost",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=False)
        assert result == "postgresql://user:pass@localhost:5432/testdb"

    def test_postgres_without_db_name(self) -> None:
        config = Settings(
            DB_SCHEME="postgresql",
            DB_NAME="",
            DB_USER="user",
            DB_PASSWORD="pass",
            DB_HOST="localhost",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=True)
        assert result == "postgresql+asyncpg://user:pass@localhost:5432"

    def test_postgres_custom_port(self) -> None:
        config = Settings(
            DB_SCHEME="postgresql",
            DB_NAME="testdb",
            DB_USER="user",
            DB_PASSWORD="pass",
            DB_HOST="db.example.com",
            DB_PORT=5433,
        )
        result = build_db_url(config, async_db=True)
        assert result == "postgresql+asyncpg://user:pass@db.example.com:5433/testdb"

    def test_postgres_special_chars_in_password(self) -> None:
        config = Settings(
            DB_SCHEME="postgresql",
            DB_NAME="testdb",
            DB_USER="user",
            DB_PASSWORD="p@ss:word!",
            DB_HOST="localhost",
            DB_PORT=5432,
        )
        result = build_db_url(config, async_db=True)
        assert result == "postgresql+asyncpg://user:p@ss:word!@localhost:5432/testdb"
