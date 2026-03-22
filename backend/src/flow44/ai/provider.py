from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm

from flow44.config import settings
from flow44.ai.core.messages import Message


# TODO: when will messages be dicts?
def _to_dicts(messages: list[dict | Message]) -> list[dict]:
    return [m.to_dict() if isinstance(m, Message) else m for m in messages]

# TODO: move llmlite langfuse code here?

async def complete_chat(
    messages: list[dict | Message],
    system_prompt: str,
    model: str | None = None,
    metadata: dict | None = None,
) -> str:
    resolved_model = model or settings.AI_MODEL
    full_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_to_dicts(messages),
    ]

    response = await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        stream=False,
        metadata=metadata or {},
    )

    content = response.choices[0].message.content
    if content is None:
        raise ValueError("LLM returned empty response")
    return content


async def complete_chat_with_tools(
    messages: list[dict | Message],
    system_prompt: str,
    tools: list[dict],
    model: str | None = None,
    metadata: dict | None = None,
    tool_choice: str = "auto",
):
    resolved_model = model or settings.AI_MODEL
    full_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_to_dicts(messages),
    ]

    return await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        tools=tools,
        tool_choice=tool_choice,
        stream=False,
        metadata=metadata or {},
    )


async def stream_chat(
    messages: list[dict | Message],
    system_prompt: str,
    model: str | None = None,
    metadata: dict | None = None,
) -> AsyncIterator[str]:
    resolved_model = model or settings.AI_MODEL
    full_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_to_dicts(messages),
    ]

    response = await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        stream=True,
        metadata=metadata or {},
    )

    async for chunk in response:
        delta = chunk.choices[0].delta  # type: ignore[union-attr]
        content = getattr(delta, "content", None)
        if content:
            yield content
