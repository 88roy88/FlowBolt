from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class PlatformUserGroup(SQLModel, table=True):
    __tablename__ = "platform_user_groups"

    # group's AD distinguishedName — the id the directory service reports in a user's memberOf.
    group_id: str = Field(primary_key=True)
    # display-only snapshots captured at invite time; never used for access decisions.
    group_name: str = Field(default="")
    email: str = Field(default="")
    invited_by: str = Field(default="")
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


async def add_platform_group(group_id: str, group_name: str, invited_by: str, email: str = "") -> PlatformUserGroup:
    group = PlatformUserGroup(group_id=group_id, group_name=group_name, invited_by=invited_by, email=email)
    async with database.async_session() as session:
        session.add(group)
        await session.commit()
        await session.refresh(group)
    return group


async def remove_platform_group(group_id: str) -> bool:
    async with database.async_session() as session:
        group = await session.get(PlatformUserGroup, group_id)
        if not group:
            return False
        await session.delete(group)
        await session.commit()
        return True


async def list_platform_groups() -> list[PlatformUserGroup]:
    async with database.async_session() as session:
        result = await session.execute(select(PlatformUserGroup).order_by(col(PlatformUserGroup.created_at).desc()))
        return list(result.scalars().all())


async def platform_group_ids() -> set[str]:
    """DNs of every group granted platform access (empty if none)."""
    async with database.async_session() as session:
        result = await session.execute(select(PlatformUserGroup.group_id))
        return set(result.scalars().all())
