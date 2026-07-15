"""Platform access granted to a whole directory group.

Mirrors :class:`~flow44.db.platform_user.PlatformUser`, but the principal is a
group (identified by its stable AD ``objectGUID``) rather than an individual. A
user gains platform access if ADAPI reports them as a member of any granted
group — the same "verify by group membership" pattern the project-level
:mod:`flow44.db.project_member_group` grants use.
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class PlatformUserGroup(SQLModel, table=True):
    __tablename__ = "platform_user_groups"

    # AD objectGUID of the group. Stable across renames/moves (unlike DN or name).
    group_id: str = Field(primary_key=True)
    # Human-readable name, cached for display so the admin UI need not re-query
    # ADAPI. Not used for access decisions.
    group_name: str = Field(default="")
    invited_by: str = Field(default="")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def add_platform_group(group_id: str, group_name: str, invited_by: str) -> PlatformUserGroup:
    group = PlatformUserGroup(group_id=group_id, group_name=group_name, invited_by=invited_by)
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
        result = await session.execute(
            select(PlatformUserGroup).order_by(col(PlatformUserGroup.created_at).desc())
        )
        return list(result.scalars().all())


async def platform_group_ids() -> set[str]:
    """objectGUIDs of every group granted platform access (empty if none)."""
    async with database.async_session() as session:
        result = await session.execute(select(PlatformUserGroup.group_id))
        return set(result.scalars().all())
