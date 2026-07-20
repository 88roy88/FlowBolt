import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, ForeignKey, String
from sqlmodel import Field, SQLModel, col, select

from flow44.db import database


class ChatRole(StrEnum):
    user = "user"
    assistant = "assistant"
    tool_call = "tool_call"
    tool_result = "tool_result"
    reasoning = "reasoning"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    project_id: str = Field(sa_column=Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False))
    role: ChatRole
    content: str
    # The literal LLM message dict (role/content/tool_calls, or role="tool"/tool_call_id) for
    # tool_call and tool_result rows — lets history be replayed as the real conversation instead
    # of a paraphrased summary. None for user/assistant/reasoning rows.
    raw_message: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


async def save_message(
    project_id: str, role: ChatRole, content: str, raw_message: dict[str, Any] | None = None
) -> ChatMessage:
    """Persist a chat message and return it."""
    msg = ChatMessage(project_id=project_id, role=role, content=content, raw_message=raw_message)
    async with database.async_session() as session:
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
    return msg


async def get_messages(project_id: str) -> list[ChatMessage]:
    """Return all messages for a project in chronological order."""
    async with database.async_session() as session:
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.project_id == project_id).order_by(col(ChatMessage.created_at).asc())
        )
        return list(result.scalars().all())
