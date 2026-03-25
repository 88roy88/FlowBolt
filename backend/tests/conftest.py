import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import flow44.config
import flow44.db.database
from flow44.config import Settings
from flow44.db.database import get_engine, init_db, reset


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(scope="session")
async def setup_test_db(tmp_path_factory: pytest.TempPathFactory):
    """Session-scoped: create engine and tables once for all tests."""
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["AIB_DATABASE_URL"] = f"sqlite:///{db_path}"

    flow44.config.settings = Settings()
    await reset()
    await init_db()

    yield db_path

    await reset()
    db_path.unlink(missing_ok=True)


@pytest.fixture
async def test_db(setup_test_db):
    """Function-scoped: wrap each test in a transaction that gets rolled back."""
    engine = get_engine()
    original_async_session = flow44.db.database.async_session

    async with engine.connect() as conn:
        trans = await conn.begin()
        bound_factory = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)

        flow44.db.database.async_session = lambda: bound_factory()

        async with bound_factory() as session:
            yield session

        flow44.db.database.async_session = original_async_session
        await trans.rollback()
