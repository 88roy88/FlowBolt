"""Chat message model and persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel, select

from flow44.db.database import async_session


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(foreign_key="projects.id")
    role: str  # "user" | "assistant"
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def save_message(project_id: str, role: str, content: str) -> ChatMessage:
    """Persist a chat message and return it."""
    msg = ChatMessage(project_id=project_id, role=role, content=content)
    async with async_session() as session:
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
    return msg


async def get_messages(project_id: str) -> list[ChatMessage]:
    """Return all messages for a project in chronological order."""
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.project_id == project_id)
            .order_by(ChatMessage.created_at.asc())  # type: ignore[arg-type]
        )
        return list(result.scalars().all())
