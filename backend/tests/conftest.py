import os
from pathlib import Path
from dotenv import load_dotenv

# Load test.env to satisfy required environment variables in tests
load_dotenv(Path(__file__).parent.parent / "test.env")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import flow44.config
import flow44.db.database
from flow44.db.database import get_engine, init_db, reset


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(scope="session")
async def setup_test_db():
    """Session-scoped: create engine and tables once for all tests."""

    await reset()
    await init_db()
    
    # Create tables for the test session
    from sqlmodel import SQLModel
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

        flow44.db.database.async_session = lambda: bound_factory()

        async with bound_factory() as session:
            yield session

        flow44.db.database.async_session = original_async_session
        await trans.rollback()
