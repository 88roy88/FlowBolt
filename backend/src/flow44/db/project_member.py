import uuid
from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import defer
from sqlmodel import Field, SQLModel, col, select

from flow44.auth.permissions import Role
from flow44.db import database
from flow44.db.project import Project


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    user_id: str = Field(index=True)
    role: str = Field(default=Role.viewer.value)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    invited_by: str = Field(default="")


async def add_member(project_id: str, user_id: str, role: Role, invited_by: str) -> ProjectMember:
    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
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


async def list_shared_projects(user_id: str) -> list[tuple[Project, Role]]:
    """Returns projects shared with the user and their role."""
    async with database.async_session() as session:
        result = await session.execute(
            select(Project, ProjectMember.role)
            .join(ProjectMember, col(ProjectMember.project_id) == col(Project.id))
            .where(col(ProjectMember.user_id) == user_id)
            .order_by(col(Project.created_at).desc())
            .options(defer(Project.data_sources))  # type: ignore[arg-type]
        )
        return [(row[0], Role(row[1])) for row in result.all()]
