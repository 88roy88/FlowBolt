import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import Field, SQLModel, select

from flow44.db import database


class ChatRole(StrEnum):
    user = "user"
    assistant = "assistant"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False))
    role: ChatRole
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def save_message(project_id: str, role: ChatRole, content: str) -> ChatMessage:
    """Persist a chat message and return it."""
    msg = ChatMessage(project_id=project_id, role=role, content=content)
    async with database.async_session() as session:
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
    return msg


async def get_messages(project_id: str) -> list[ChatMessage]:
    """Return all messages for a project in chronological order."""
    async with database.async_session() as session:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.project_id == project_id).order_by(ChatMessage.created_at.asc())  # type: ignore[arg-type]
        )
        return list(result.scalars().all())
