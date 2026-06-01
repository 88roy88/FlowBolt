from pathlib import Path

import pytest  # noqa: E402
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

# Load test.env to satisfy required environment variables in tests
# Must happen before importing flow44.config (which reads env vars)
load_dotenv(Path(__file__).parent / "test.env")

import flow44.config  # noqa: E402
import flow44.db.database  # noqa: E402
from flow44.db.database import get_engine, init_db, reset  # noqa: E402


@pytest.fixture(autouse=True)
def auth_test_user():
    """Authenticate all HTTP TestClient requests as a fixed test user.

    Every REST route is mounted behind ``Depends(get_user_id)`` (the central auth
    choke-point in ``main.py``). Overriding it here lets endpoint tests exercise
    routes without minting tokens. Auth unit tests call ``get_user_id`` directly
    (not through the app) and so are unaffected; WS auth (``get_ws_user_id``) is
    intentionally left untouched.
    """
    from flow44.api.deps import get_user_id  # noqa: PLC0415
    from flow44.main import app  # noqa: PLC0415

    app.dependency_overrides[get_user_id] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(get_user_id, None)


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(scope="session")
async def setup_test_db():
    """Session-scoped: create engine and tables once for all tests."""

    await reset()
    await init_db()

    # Create tables for the test session
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
