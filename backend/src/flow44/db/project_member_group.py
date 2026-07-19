import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint
from sqlmodel import Field, SQLModel, col, select

from flow44.auth.permissions import Role
from flow44.db import database
from flow44.db.project import Project


class ProjectMemberGroup(SQLModel, table=True):
    """A directory group granted access to a project (a "group invite").

    Mirrors :class:`~flow44.db.project_member.ProjectMember`, but the principal
    is a group (identified by its AD ``distinguishedName``) rather than a user.
    A user gains the group's role on the project if ADAPI reports them as a
    member of ``group_id``.
    """

    __tablename__ = "project_member_groups"
    __table_args__ = (UniqueConstraint("project_id", "group_id", name="uq_project_member_group"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(
        sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    # AD distinguishedName (DN) of the group — the identifier ADAPI reports in a
    # user's ``memberOf``, so access resolution intersects on it directly.
    group_id: str = Field(index=True)
    # Human-readable group name, cached for display so the members UI need not
    # re-query ADAPI. Not used for access decisions.
    group_name: str = Field(default="")
    role: str = Field(default=Role.viewer.value)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    invited_by: str = Field(default="")


async def add_group(
    project_id: str, group_id: str, group_name: str, role: Role, invited_by: str
) -> ProjectMemberGroup:
    grant = ProjectMemberGroup(
        project_id=project_id,
        group_id=group_id,
        group_name=group_name,
        role=role.value,
        invited_by=invited_by,
    )
    async with database.async_session() as session:
        session.add(grant)
        await session.commit()
        await session.refresh(grant)
    return grant


async def remove_group(project_id: str, group_id: str) -> bool:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMemberGroup).where(
                ProjectMemberGroup.project_id == project_id,
                ProjectMemberGroup.group_id == group_id,
            )
        )
        grant = result.scalar_one_or_none()
        if not grant:
            return False
        await session.delete(grant)
        await session.commit()
        return True


async def update_group_role(project_id: str, group_id: str, role: Role) -> ProjectMemberGroup | None:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMemberGroup).where(
                ProjectMemberGroup.project_id == project_id,
                ProjectMemberGroup.group_id == group_id,
            )
        )
        grant = result.scalar_one_or_none()
        if not grant:
            return None
        grant.role = role.value
        session.add(grant)
        await session.commit()
        await session.refresh(grant)
        return grant


async def list_group_shared_projects(group_ids: set[str]) -> list[tuple[Project, Role]]:
    """Projects shared with the user via directory-group grants, and the group's role.

    ``group_ids`` is the user's (transitive) group membership, as resolved by
    ADAPI. A project may be granted to several of the user's groups; each matching
    grant is returned as its own ``(project, role)`` row, so the caller unions the
    roles across sources. Short-circuits without a query when the user is in no
    groups.
    """
    if not group_ids:
        return []
    async with database.async_session() as session:
        result = await session.execute(
            select(Project, ProjectMemberGroup.role)
            .join(ProjectMemberGroup, col(ProjectMemberGroup.project_id) == col(Project.id))
            .where(col(ProjectMemberGroup.group_id).in_(group_ids))
            .order_by(col(Project.created_at).desc())
        )
        return [(row[0], Role(row[1])) for row in result.all()]


async def list_project_groups(project_id: str) -> list[ProjectMemberGroup]:
    async with database.async_session() as session:
        result = await session.execute(
            select(ProjectMemberGroup)
            .where(ProjectMemberGroup.project_id == project_id)
            .order_by(col(ProjectMemberGroup.created_at).asc())
        )
        return list(result.scalars().all())
