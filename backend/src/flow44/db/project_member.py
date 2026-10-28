import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, and_, func, or_, tuple_
from sqlmodel import Field, SQLModel, col, select

from flow44.auth.permissions import Role, highest_role
from flow44.db import database
from flow44.db.project import Project
from flow44.db.project_member_group import ProjectMemberGroup


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(
        sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    user_id: str = Field(index=True)
    display_name: str = Field(default="")
    role: str = Field(default=Role.viewer.value)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    invited_by: str = Field(default="")


async def add_member(
    project_id: str, user_id: str, role: Role, invited_by: str, display_name: str = ""
) -> ProjectMember:
    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        display_name=display_name,
        role=role.value,
        invited_by=invited_by,
    )
    async with database.async_session() as session:
        session.add(member)
        await session.commit()
        await session.refresh(member)
    return member


async def remove_member(project_id: str, user_id: str) -> bool:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False
        await session.delete(member)
        await session.commit()
        return True


async def update_member_role(project_id: str, user_id: str, role: Role) -> ProjectMember | None:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return None
        member.role = role.value
        session.add(member)
        await session.commit()
        await session.refresh(member)
        return member


async def get_project_member(project_id: str, user_id: str) -> ProjectMember | None:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()


async def list_project_members(project_id: str) -> list[ProjectMember]:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .order_by(col(ProjectMember.created_at).asc())
        )
        return list(result.scalars().all())


async def list_projects_for_user(
    user_id: str,
    *,
    group_ids: Collection[str] = (),
    include_all: bool = False,
    name_query: str = "",
    before: tuple[str, str] | None = None,
    limit: int,
) -> list[tuple[Project, Role | None]]:
    """Return a page of projects visible to the user, each with the highest role granted directly or via a group."""
    query = select(Project, ProjectMember.role).outerjoin(
        ProjectMember,
        and_(col(ProjectMember.project_id) == col(Project.id), col(ProjectMember.user_id) == user_id),
    )
    if not include_all:
        group_shared = select(ProjectMemberGroup.project_id).where(col(ProjectMemberGroup.group_id).in_(group_ids))
        query = query.where(
            or_(
                col(Project.user_id) == user_id,
                col(ProjectMember.id).is_not(None),
                col(Project.id).in_(group_shared),
            )
        )
    if name_query:
        query = query.where(col(Project.name).icontains(name_query, autoescape=True))
    if before is not None:
        query = query.where(tuple_(col(Project.created_at), col(Project.id)) < before)
    query = query.order_by(col(Project.created_at).desc(), col(Project.id).desc()).limit(limit)

    async with database.async_session() as session:
        rows = (await session.execute(query)).all()
        granted: dict[str, list[Role]] = {row[0].id: [Role(row[1])] if row[1] is not None else [] for row in rows}
        if group_ids and rows:
            grants = await session.execute(
                select(ProjectMemberGroup.project_id, ProjectMemberGroup.role).where(
                    col(ProjectMemberGroup.project_id).in_(list(granted)),
                    col(ProjectMemberGroup.group_id).in_(group_ids),
                )
            )
            for project_id, role in grants.all():
                granted[project_id].append(Role(role))

    return [(row[0], highest_role(granted[row[0].id])) for row in rows]
