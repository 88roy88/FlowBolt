import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import IntEnum

from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from flow44.config import settings
from flow44.db import database

_LOCK_NOT_AVAILABLE = "55P03"


class LockNamespace(IntEnum):
    workspace = 1


class LockTimeout(RuntimeError):
    pass


_local: defaultdict[tuple[LockNamespace, str], asyncio.Lock] = defaultdict(asyncio.Lock)


async def _limit_lock_time(session: AsyncSession) -> None:
    await session.execute(
        select(
            func.set_config("lock_timeout", f"{settings.ADVISORY_LOCK_WAIT_TIMEOUT}s", True),
            func.set_config("idle_in_transaction_session_timeout", f"{settings.ADVISORY_LOCK_HOLD_TIMEOUT}s", True),
        )
    )


async def _acquire(session: AsyncSession, namespace: LockNamespace, key: str) -> None:
    try:
        await session.execute(select(func.pg_advisory_xact_lock(int(namespace), func.hashtext(key))))
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE:
            raise LockTimeout(f"{namespace.name}:{key}") from exc
        raise


@asynccontextmanager
async def advisory_lock(namespace: LockNamespace, key: str) -> AsyncIterator[None]:
    # Queue in-process first so a waiter doesn't hold a pooled connection.
    async with _local[namespace, key], database.async_session() as session, session.begin():
        await _limit_lock_time(session)
        await _acquire(session, namespace, key)
        yield
