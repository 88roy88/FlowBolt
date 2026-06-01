from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import litellm

from flow44.ai.core.messages import Message
from flow44.config import settings

logger = logging.getLogger(__name__)


# TODO: when will messages be dicts?
def _to_dicts(messages: list[dict[str, Any] | Message]) -> list[dict[str, Any]]:
    return [m.to_dict() if isinstance(m, Message) else m for m in messages]


# TODO: move llmlite langfuse code here?


@asynccontextmanager
async def _handle_litellm_errors(model: str | None = None) -> AsyncIterator[None]:
    resolved_model = model or settings.AI_MODEL
    try:
        yield
    except litellm.InternalServerError as exc:
        logger.error(
            "[provider] LiteLLM InternalServerError | model=%s status=%s message=%s",
            resolved_model,
            getattr(exc, "status_code", "?"),
            getattr(exc, "message", str(exc)),
        )
        raise
    except Exception:
        logger.exception("[provider] Unexpected error calling LiteLLM | model=%s", resolved_model)
        raise


async def complete_chat(
    messages: list[dict[str, Any] | Message],
    system_prompt: str,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    resolved_model = _normalize_model(model or settings.AI_MODEL)
    full_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_to_dicts(messages),
    ]

    async with _handle_litellm_errors(resolved_model):
        response = await litellm.acompletion(
            model=resolved_model,
            messages=full_messages,
            api_base=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            stream=False,
            metadata=metadata or {},
        )

    content: str | None = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned empty response")
    return content


async def complete_chat_with_tools(
    messages: list[dict[str, Any] | Message],
    system_prompt: str,
    tools: list[dict[str, Any]],
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
    tool_choice: str = "auto",
) -> Any:
    resolved_model = _normalize_model(model or settings.AI_MODEL)
    full_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_to_dicts(messages),
    ]

    async with _handle_litellm_errors(resolved_model):
        return await litellm.acompletion(
            model=resolved_model,
            messages=full_messages,
            api_base=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            tools=tools,
            tool_choice=tool_choice,
            stream=False,
            metadata=metadata or {},
        )


async def stream_chat(
    messages: list[dict[str, Any] | Message],
    system_prompt: str,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    resolved_model = _normalize_model(model or settings.AI_MODEL)
    full_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_to_dicts(messages),
    ]

    async with _handle_litellm_errors(resolved_model):
        response = await litellm.acompletion(
            model=resolved_model,
            messages=full_messages,
            api_base=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
            stream=True,
            metadata=metadata or {},
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content
