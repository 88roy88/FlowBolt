"""
OpenAI-compatible completions mock for testing Langchain without a real model.
Exposes POST /v1/chat/completions and POST /v1/completions.
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Model Mock", description="OpenAI-compatible completions mock")

# Optional: return a fixed HTML body for tests (set via env MOCK_HTML_RESPONSE).
# Default includes <Library:Lodash /> placeholder and LIBRARIES_USED line for server injection tests.
DEFAULT_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><Library:Lodash /></head><body><p>Generated chart</p></body></html>
LIBRARIES_USED: lodash"""


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


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    """Echo or return configured HTML so agent tests are deterministic."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_json", "message": "Invalid JSON body"}},
        )
    messages = body.get("messages") or []
    model = body.get("model", "mock-model")
    # Return fixed HTML from env or a minimal placeholder so agent can parse it
    content = os.environ.get("MOCK_HTML_RESPONSE", DEFAULT_HTML)
    # Optional: append echoed user prompt for debugging
    if os.environ.get("MOCK_ECHO_USER") == "1":
        last = _get_last_user_content(messages)
        if last:
            content = content.rstrip() + f"\n<!-- user: {last[:200]} -->"

    return JSONResponse(
        content={
            "id": "mock-cmpl-1",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
    )


@app.post("/v1/completions")
async def completions(request: Request) -> JSONResponse:
    """Legacy text completions compatibility endpoint."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_json", "message": "Invalid JSON body"}},
        )

    model = body.get("model", "mock-model")
    content = os.environ.get("MOCK_HTML_RESPONSE", DEFAULT_HTML)
    prompt = body.get("prompt", "")
    if os.environ.get("MOCK_ECHO_USER") == "1" and isinstance(prompt, str) and prompt:
        content = content.rstrip() + f"\n<!-- prompt: {prompt[:200]} -->"

    return JSONResponse(
        content={
            "id": "mock-cmpl-legacy-1",
            "object": "text_completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "text": content,
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
