"""AI provider using LiteLLM for multi-provider model access."""

from __future__ import annotations

from collections.abc import AsyncIterator

import litellm

from app.config import settings


async def complete_chat(
    messages: list[dict],
    system_prompt: str,
    model: str | None = None,
) -> str:
    """Non-streaming completion for classification, planning, merging.

    Parameters
    ----------
    messages:
        Conversation history as a list of ``{"role": ..., "content": ...}`` dicts.
    system_prompt:
        Prepended as a ``system`` message at the start of the conversation.
    model:
        LiteLLM model identifier.  Falls back to ``settings.AI_MODEL``.
    """
    resolved_model = model or settings.AI_MODEL

    full_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        *messages,
    ]

    response = await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        stream=False,
    )

    return response.choices[0].message.content


async def stream_chat(
    messages: list[dict],
    system_prompt: str,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream an AI chat completion, yielding content deltas.

    Parameters
    ----------
    messages:
        Conversation history as a list of ``{"role": ..., "content": ...}`` dicts.
    system_prompt:
        Prepended as a ``system`` message at the start of the conversation.
    model:
        LiteLLM model identifier.  Falls back to ``settings.AI_MODEL``.
    """
    resolved_model = model or settings.AI_MODEL

    full_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        *messages,
    ]

    response = await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        stream=True,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta  # type: ignore[union-attr]
        content = getattr(delta, "content", None)
        if content:
            yield content
