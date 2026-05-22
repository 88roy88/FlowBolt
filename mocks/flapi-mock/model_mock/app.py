"""
OpenAI-compatible completions mock for testing Langchain without a real model.
Exposes POST /v1/chat/completions and POST /v1/completions.
"""
from __future__ import annotations

import os
import time
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Model Mock", description="OpenAI-compatible completions mock")

# Optional: return a fixed HTML body for tests (set via env MOCK_HTML_RESPONSE).
# Default includes <Library:Lodash /> placeholder and LIBRARIES_USED line for server injection tests.
DEFAULT_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><Library:Lodash /></head><body><p>Generated chart</p></body></html>
LIBRARIES_USED: lodash"""


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str | list[dict[str, Any]] | None = None


class ChatCompletionsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    messages: list[ChatMessage] = Field(default_factory=list)
    model: str = "mock-model"


class CompletionsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str | list[str] | None = None
    model: str = "mock-model"


class ChatChoiceMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: Literal["stop"] = "stop"


class TextChoice(BaseModel):
    index: int = 0
    text: str
    logprobs: None = None
    finish_reason: Literal["stop"] = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 10
    completion_tokens: int = 20
    total_tokens: int = 30


class ChatCompletionsResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: Usage


class CompletionsResponse(BaseModel):
    id: str
    object: Literal["text_completion"] = "text_completion"
    created: int
    model: str
    choices: list[TextChoice]
    usage: Usage


def _get_last_user_content(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        return part.get("text", "")
            return ""
    return ""


@app.post(
    "/v1/chat/completions",
    response_model=ChatCompletionsResponse,
    summary="OpenAI-compatible chat completions",
)
async def chat_completions(request: Request) -> JSONResponse:
    """Echo or return configured HTML so agent tests are deterministic."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_json", "message": "Invalid JSON body"}},
        )
    parsed = ChatCompletionsRequest.model_validate(body)
    messages = [m.model_dump() for m in parsed.messages]
    # Return fixed HTML from env or a minimal placeholder so agent can parse it
    content = os.environ.get("MOCK_HTML_RESPONSE", DEFAULT_HTML)
    # Optional: append echoed user prompt for debugging
    if os.environ.get("MOCK_ECHO_USER") == "1":
        last = _get_last_user_content(messages)
        if last:
            content = content.rstrip() + f"\n<!-- user: {last[:200]} -->"

    response = ChatCompletionsResponse(
        id="mock-cmpl-1",
        created=int(time.time()),
        model=parsed.model,
        choices=[
            ChatChoice(message=ChatChoiceMessage(content=content)),
        ],
        usage=Usage(),
    )
    return JSONResponse(content=response.model_dump())


@app.post(
    "/v1/completions",
    response_model=CompletionsResponse,
    summary="OpenAI-compatible legacy text completions",
)
async def completions(request: Request) -> JSONResponse:
    """Legacy text completions compatibility endpoint."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_json", "message": "Invalid JSON body"}},
        )

    parsed = CompletionsRequest.model_validate(body)
    content = os.environ.get("MOCK_HTML_RESPONSE", DEFAULT_HTML)
    prompt = parsed.prompt
    if os.environ.get("MOCK_ECHO_USER") == "1" and isinstance(prompt, str) and prompt:
        content = content.rstrip() + f"\n<!-- prompt: {prompt[:200]} -->"

    response = CompletionsResponse(
        id="mock-cmpl-legacy-1",
        created=int(time.time()),
        model=parsed.model,
        choices=[TextChoice(text=content)],
        usage=Usage(),
    )
    return JSONResponse(content=response.model_dump())


@app.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
