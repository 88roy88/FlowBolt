from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from flow44.api.deps import UserDep
from flow44.config import settings
from flow44.feature_flags import get_enabled_flags

router = APIRouter(prefix="/api/config", tags=["config"])


class ClientConfigResponse(BaseModel):
    chat_message_max_chars: int
    features: list[str]


@router.get("")
async def client_config(user_id: UserDep) -> ClientConfigResponse:
    return ClientConfigResponse(
        chat_message_max_chars=settings.CHAT_MESSAGE_MAX_CHARS,
        features=sorted(await get_enabled_flags(user_id)),
    )
