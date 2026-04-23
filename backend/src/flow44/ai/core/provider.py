from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm

from flow44.ai.core.messages import Message
from flow44.config import settings

# litellm uses "<provider>/<model>" for provider routing. Some docs (and our
# example.env) show the colon form ("bedrock:us.anthropic..."), so normalize
# the first colon to a slash for the prefixes we support.
_LITELLM_PROVIDER_PREFIXES = ("bedrock", "anthropic", "openai", "openrouter", "vertex_ai")

# These providers use native SDK auth (boto/AWS creds, ANTHROPIC_API_KEY, GCP
# app-default creds) rather than an OpenAI-compatible base URL + API key.
# Passing AI_BASE_URL/AI_API_KEY to them breaks provider routing or auth.
_NATIVE_AUTH_PROVIDERS = ("bedrock", "anthropic", "vertex_ai")


def _normalize_model(model: str) -> str:
    provider, sep, rest = model.partition(":")
    if sep and provider in _LITELLM_PROVIDER_PREFIXES:
        return f"{provider}/{rest}"
    return model


def _litellm_auth(model: str) -> tuple[str | None, str | None]:
    # Returns (api_base, api_key). Native providers (Bedrock, Anthropic, Vertex)
    # use SDK-level auth (AWS/boto, ANTHROPIC_API_KEY, GCP ADC); passing our
    # OpenAI-compatible base URL to them breaks provider routing.
    provider = model.split("/", 1)[0]
    if provider in _NATIVE_AUTH_PROVIDERS:
        return None, None
    return settings.AI_BASE_URL, settings.AI_API_KEY


# TODO: when will messages be dicts?
def _to_dicts(messages: list[dict[str, Any] | Message]) -> list[dict[str, Any]]:
    return [m.to_dict() if isinstance(m, Message) else m for m in messages]


# TODO: move llmlite langfuse code here?


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

    api_base, api_key = _litellm_auth(resolved_model)
    response = await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        api_base=api_base,
        api_key=api_key,
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

    api_base, api_key = _litellm_auth(resolved_model)
    return await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        api_base=api_base,
        api_key=api_key,
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

    api_base, api_key = _litellm_auth(resolved_model)
    response = await litellm.acompletion(
        model=resolved_model,
        messages=full_messages,
        api_base=api_base,
        api_key=api_key,
        stream=True,
        metadata=metadata or {},
    )

    async for chunk in response:
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content
