"""Chat message persistence using aiosqlite."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite

from flow44.models.project import _get_db_path


# TODO: why not pydantic?
@dataclass
class ChatMessage:
    id: str
    project_id: str
    # TODO: use literal
    role: str  # "user" | "assistant"
    content: str
    created_at: str


async def save_message(project_id: str, role: str, content: str) -> ChatMessage:
    """Persist a chat message and return it."""
    msg = ChatMessage(
        id=str(uuid.uuid4()),
        project_id=project_id,
        role=role,
        content=content,
        created_at=datetime.now(UTC).isoformat(),
    )
    async with aiosqlite.connect(_get_db_path()) as db:
        await db.execute(
            "INSERT INTO chat_messages (id, project_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg.id, msg.project_id, msg.role, msg.content, msg.created_at),
        )
        await db.commit()
    return msg


async def get_messages(project_id: str) -> list[ChatMessage]:
    """Return all messages for a project in chronological order."""
    async with aiosqlite.connect(_get_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chat_messages WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [ChatMessage(**dict(r)) for r in rows]
