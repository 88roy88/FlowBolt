import pytest
from sqlalchemy import func, select

from flow44.db import database
from flow44.db.locks import LockNamespace, advisory_lock

pytestmark = pytest.mark.asyncio


async def _held_elsewhere(key: str) -> bool:
    async with database.get_engine().connect() as other_pod:
        return not await other_pod.scalar(
            select(func.pg_try_advisory_xact_lock(LockNamespace.workspace, func.hashtext(key)))
        )


async def test_lock_is_held_across_connections_until_exit(setup_test_db) -> None:  # type: ignore[no-untyped-def]
    async with advisory_lock(LockNamespace.workspace, "project-1"):
        assert await _held_elsewhere("project-1")
        assert not await _held_elsewhere("project-2")

    assert not await _held_elsewhere("project-1")
