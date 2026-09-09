import contextlib
import functools
import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Load test.env to satisfy required environment variables in tests
# Must happen before importing flow44.config (which reads env vars)
load_dotenv(Path(__file__).parent / "test.env")

import flow44.config  # noqa: E402
import flow44.db.database  # noqa: E402
from flow44.api.deps import (  # noqa: E402
    TokenPayload,
    get_user_id,
    get_user_permissions,
    validate_token,
    validate_ws_token,
)
from flow44.auth.permissions import get_owner_permissions  # noqa: E402
from flow44.db.database import build_db_url, init_db, reset  # noqa: E402
from flow44.main import app  # noqa: E402


@functools.lru_cache
def get_engine(url: str | None = None) -> AsyncEngine:
    # asyncpg connections can't be reused across pytest's per-test event loops,
    # so tests use NullPool instead of the production QueuePool.
    async_url = url or build_db_url(flow44.config.settings)
    return create_async_engine(async_url, echo=False, poolclass=NullPool)


flow44.db.database.get_engine = get_engine


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(autouse=True)
def authenticated_user():
    # HTTP/WS tests act as a signed-in user with full permissions;
    # auth/permission tests call the deps directly and bypass this.
    payload = TokenPayload(exp=9_999_999_999, unique_id="test-user")
    app.dependency_overrides[get_user_id] = lambda: "test-user"
    app.dependency_overrides[validate_token] = lambda: payload
    app.dependency_overrides[validate_ws_token] = lambda: payload
    app.dependency_overrides[get_user_permissions] = lambda: get_owner_permissions()
    yield
    app.dependency_overrides.pop(get_user_id, None)
    app.dependency_overrides.pop(validate_token, None)
    app.dependency_overrides.pop(validate_ws_token, None)
    app.dependency_overrides.pop(get_user_permissions, None)


@pytest.fixture(scope="session")
async def setup_test_db():
    """Session-scoped: create an isolated database on the running Postgres and build tables once."""
    from pytest_postgresql.janitor import DatabaseJanitor  # noqa: PLC0415

    settings = flow44.config.settings
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    dbname = f"test_flow44_{worker}"

    janitor = DatabaseJanitor(
        user=settings.DB_USER,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=dbname,
        version="16",
        password=settings.DB_PASSWORD,
    )
    # Pre-drop the DB if it exists from prior aborted runs (suppresses error if it doesn't exist yet).
    with contextlib.suppress(psycopg.errors.InvalidCatalogName):
        janitor.drop()

    with janitor:
        settings.DB_NAME = dbname
        await reset()
        await init_db()

        from sqlmodel import SQLModel  # noqa: PLC0415

        async with get_engine().begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        yield

        await reset()


@pytest.fixture
async def test_db(setup_test_db):
    """Function-scoped: wrap each test in a transaction that gets rolled back."""
    engine = get_engine()
    original_async_session = flow44.db.database.async_session

    async with engine.connect() as conn:
        trans = await conn.begin()
        bound_factory = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)

        flow44.db.database.async_session = lambda: bound_factory()  # noqa: PLW0108

        async with bound_factory() as session:
            yield session

        flow44.db.database.async_session = original_async_session
        await trans.rollback()
