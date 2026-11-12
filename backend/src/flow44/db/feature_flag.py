from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class FlagTargetType(StrEnum):
    user = "user"
    group = "group"


class FeatureFlagSetting(SQLModel, table=True):
    __tablename__ = "feature_flags"

    key: str = Field(primary_key=True)
    enabled_for_all: bool = Field(default=False)
    enabled_for_admins: bool = Field(default=False)
    updated_by: str = Field(default="")
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


class FeatureFlagTarget(SQLModel, table=True):
    """A user (UniqueID, casefolded) or directory group (DN) a flag is turned on for."""

    __tablename__ = "feature_flag_targets"

    flag_key: str = Field(
        sa_column=Column(String, ForeignKey("feature_flags.key", ondelete="CASCADE"), primary_key=True)
    )
    target_type: str = Field(primary_key=True)
    target_id: str = Field(primary_key=True)
    display_name: str = Field(default="")
    email: str = Field(default="")
    added_by: str = Field(default="")
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


@dataclass
class FlagState:
    key: str
    enabled_for_all: bool = False
    enabled_for_admins: bool = False
    targets: list[FeatureFlagTarget] = field(default_factory=list)


async def list_flag_states(keys: Iterable[str]) -> dict[str, FlagState]:
    keys = list(keys)
    async with database.async_session() as session:
        settings = (
            (await session.execute(select(FeatureFlagSetting).where(col(FeatureFlagSetting.key).in_(keys))))
            .scalars()
            .all()
        )
        targets = (
            (
                await session.execute(
                    select(FeatureFlagTarget)
                    .where(col(FeatureFlagTarget.flag_key).in_(keys))
                    .order_by(col(FeatureFlagTarget.created_at))
                )
            )
            .scalars()
            .all()
        )
    states = {
        s.key: FlagState(key=s.key, enabled_for_all=s.enabled_for_all, enabled_for_admins=s.enabled_for_admins)
        for s in settings
    }
    for target in targets:
        # The FK guarantees a settings row exists for every target.
        states[target.flag_key].targets.append(target)
    return states


async def update_flag(
    key: str,
    updated_by: str,
    initial: FlagState,
    *,
    enabled_for_all: bool | None = None,
    enabled_for_admins: bool | None = None,
) -> None:
    changes: dict[str, object] = {"updated_by": updated_by}
    if enabled_for_all is not None:
        changes["enabled_for_all"] = enabled_for_all
    if enabled_for_admins is not None:
        changes["enabled_for_admins"] = enabled_for_admins
    initial_values = {"enabled_for_all": initial.enabled_for_all, "enabled_for_admins": initial.enabled_for_admins}
    stmt = (
        insert(FeatureFlagSetting)
        .values(key=key, **(initial_values | changes))
        .on_conflict_do_update(index_elements=["key"], set_=changes | {"updated_at": func.now()})
    )
    async with database.async_session() as session:
        await session.execute(stmt)
        await session.commit()


async def add_flag_target(
    key: str,
    target_type: FlagTargetType,
    target_id: str,
    added_by: str,
    initial: FlagState,
    display_name: str = "",
    email: str = "",
) -> FeatureFlagTarget:
    """Raises IntegrityError if the target is already on this flag."""
    target = FeatureFlagTarget(
        flag_key=key,
        target_type=target_type.value,
        target_id=target_id,
        display_name=display_name,
        email=email,
        added_by=added_by,
    )
    async with database.async_session() as session:
        # Targets hang off the flag's settings row; create it from the code defaults on first use.
        await session.execute(
            insert(FeatureFlagSetting)
            .values(
                key=key,
                updated_by=added_by,
                enabled_for_all=initial.enabled_for_all,
                enabled_for_admins=initial.enabled_for_admins,
            )
            .on_conflict_do_nothing(index_elements=["key"])
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
    return target


async def remove_flag_target(key: str, target_type: FlagTargetType, target_id: str) -> bool:
    async with database.async_session() as session:
        target = await session.get(FeatureFlagTarget, (key, target_type.value, target_id))
        if target is None:
            return False
        await session.delete(target)
        await session.commit()
        return True
