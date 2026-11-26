from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from flow44.config import settings
from flow44.logic.publish_form import PublishFormConfig, get_publish_form_config

router = APIRouter(prefix="/api/config", tags=["config"])


class ClientConfig(BaseModel):
    chat_message_max_chars: int
    app_description_max_chars: int
    publish_form: PublishFormConfig


@router.get("")
async def client_config() -> ClientConfig:
    return ClientConfig(
        chat_message_max_chars=settings.CHAT_MESSAGE_MAX_CHARS,
        app_description_max_chars=settings.APP_DESCRIPTION_MAX_CHARS,
        publish_form=get_publish_form_config(),
    )
