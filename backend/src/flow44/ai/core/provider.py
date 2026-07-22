from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from opik import track
from pydantic_ai.direct import model_request
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    SystemPromptPart,
    TextPart,
    TextPartDelta,
    ToolCallPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition

from flow44.config import settings

logger = logging.getLogger(__name__)


def get_model(model_name: str | None = None) -> Model:
    resolved = model_name or settings.AI_MODEL

    if resolved.startswith("bedrock/"):
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        bedrock_model_id = resolved.removeprefix("bedrock/")
        return BedrockConverseModel(bedrock_model_id, provider=BedrockProvider())

    if resolved.startswith("openrouter/"):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        openrouter_model = resolved.removeprefix("openrouter/")
        provider = OpenAIProvider(base_url="https://openrouter.ai/api/v1", api_key=settings.AI_API_KEY or "")
        return OpenAIChatModel(openrouter_model, provider=provider)

    if settings.AI_BASE_URL:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(base_url=settings.AI_BASE_URL, api_key=settings.AI_API_KEY or "")
        return OpenAIChatModel(resolved, provider=provider)

    from pydantic_ai.models import infer_model

    return infer_model(resolved)


def _prepend_system(messages: list[ModelMessage], system_prompt: str) -> list[ModelMessage]:
    if not system_prompt:
        return messages
    return [ModelRequest(parts=[SystemPromptPart(content=system_prompt)]), *messages]


def _summarize_response(response: ModelResponse) -> dict[str, Any]:
    text_parts = [p.content for p in response.parts if isinstance(p, TextPart)]
    tool_calls = [p.tool_name for p in response.parts if isinstance(p, ToolCallPart)]
    result: dict[str, Any] = {}
    if text_parts:
        result["content"] = " ".join(text_parts)[:500]
    if tool_calls:
        result["tool_calls"] = tool_calls
    if response.usage:
        result["usage"] = {"input_tokens": response.usage.request_tokens, "output_tokens": response.usage.response_tokens}
    return result


@track(name="llm-completion", type="llm")  # type: ignore[untyped-decorator]
async def complete_chat(
    messages: list[ModelMessage],
    system_prompt: str,
    model_name: str | None = None,
) -> str:
    llm_model = get_model(model_name)
    request_messages = _prepend_system(messages, system_prompt)

    response: ModelResponse = await model_request(
        llm_model,
        request_messages,
        model_settings=ModelSettings(timeout=settings.AI_REQUEST_TIMEOUT),
        model_request_parameters=ModelRequestParameters(allow_text_output=True),
    )

    text_parts = [p for p in response.parts if isinstance(p, TextPart)]
    content = " ".join(p.content for p in text_parts)
    if not content:
        raise ValueError("LLM returned empty response")
    return content


@track(name="llm-completion-with-tools", type="llm")  # type: ignore[untyped-decorator]
async def complete_chat_with_tools(
    messages: list[ModelMessage],
    system_prompt: str,
    tool_defs: list[ToolDefinition],
    model_name: str | None = None,
) -> ModelResponse:
    llm_model = get_model(model_name)
    request_messages = _prepend_system(messages, system_prompt)

    return await model_request(
        llm_model,
        request_messages,
        model_settings=ModelSettings(timeout=settings.AI_REQUEST_TIMEOUT),
        model_request_parameters=ModelRequestParameters(
            function_tools=tool_defs,
            allow_text_output=True,
        ),
    )


@track(name="llm-stream", type="llm")  # type: ignore[untyped-decorator]
async def stream_chat(
    messages: list[ModelMessage],
    system_prompt: str,
    model_name: str | None = None,
) -> AsyncIterator[str]:
    llm_model = get_model(model_name)
    request_messages = _prepend_system(messages, system_prompt)

    async with llm_model.request_stream(
        request_messages,
        ModelSettings(timeout=settings.AI_REQUEST_TIMEOUT),
        ModelRequestParameters(allow_text_output=True),
    ) as stream:
        async for event in stream:
            if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                yield event.delta.content_delta
