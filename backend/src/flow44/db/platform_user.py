from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class PlatformUser(SQLModel, table=True):
    __tablename__ = "platform_users"

    user_id: str = Field(primary_key=True)
    invited_by: str = Field(default="")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def add_platform_user(user_id: str, invited_by: str) -> PlatformUser:
    user = PlatformUser(user_id=user_id, invited_by=invited_by)
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
