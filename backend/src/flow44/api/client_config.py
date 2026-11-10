from __future__ import annotations

from fastapi import APIRouter

from flow44.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def client_config() -> dict[str, int]:
    return {"chat_message_max_chars": settings.CHAT_MESSAGE_MAX_CHARS}
