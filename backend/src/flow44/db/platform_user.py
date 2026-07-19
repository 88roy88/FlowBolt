from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class PlatformUser(SQLModel, table=True):
    __tablename__ = "platform_users"

    user_id: str = Field(primary_key=True)
    # ADAPI displayName captured at invite time, shown as the row's primary text
    # (the email in user_id is the secondary text). Display-only, may go stale.
    display_name: str = Field(default="")
    invited_by: str = Field(default="")
    # tz-aware timestamptz column with a DB server default, mirroring
    # PlatformUserGroup — the actual column type, so ORM inserts/reads stay in
    # sync (a plain ``str`` field binds as VARCHAR and mismatches the column).
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


async def add_platform_user(user_id: str, invited_by: str, display_name: str = "") -> PlatformUser:
    user = PlatformUser(user_id=user_id, invited_by=invited_by, display_name=display_name)
    async with database.async_session() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def remove_platform_user(user_id: str) -> bool:
    async with database.async_session() as session:
        user = await session.get(PlatformUser, user_id)
        if not user:
            return False
        await session.delete(user)
        await session.commit()
        return True


async def is_platform_user(user_id: str) -> bool:
    async with database.async_session() as session:
        user = await session.get(PlatformUser, user_id)
        return user is not None


async def list_platform_users() -> list[PlatformUser]:
    async with database.async_session() as session:
        result = await session.execute(select(PlatformUser).order_by(col(PlatformUser.created_at).desc()))
        return list(result.scalars().all())
