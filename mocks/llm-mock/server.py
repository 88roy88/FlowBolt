# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.115",
#   "uvicorn[standard]>=0.34",
#   "pydantic-settings>=2.0",
# ]
# ///
"""
Mock OpenAI-compatible LLM server for e2e-v2 testing.

Endpoints:
  POST /chat/completions   — OpenAI-compatible completions (litellm calls this with api_base set)
  POST /admin/queue        — Seed the response queue (list of QueuedResponse)
  POST /admin/reset        — Clear the queue
  GET  /admin/status       — Check queue length
  GET  /health             — Health check

Queue items are popped in FIFO order per request.
If the queue is empty, returns a safe empty text response (no error) to avoid
crashing agents on unexpected LLM calls.

Env vars:
  RESPONSE_DELAY_MS   — ms to wait before serving each response (default 0).
                        Set to e.g. 1500 in headed e2e runs to make phases watchable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    RESPONSE_DELAY_MS: int = 0


settings = Settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-mock")
logger.info("Response delay: %dms", settings.RESPONSE_DELAY_MS)

app = FastAPI(title="Mock LLM Server")

_queue: deque[dict] = deque()
_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


class QueuedResponse(BaseModel):
    content: str | None = None
    tool_calls: list[dict] | None = None


@app.post("/admin/queue")
async def push_to_queue(responses: list[QueuedResponse]):
    async with _lock:
        for r in responses:
            _queue.append(r.model_dump())
    logger.info("Queued %d responses (total: %d)", len(responses), len(_queue))
    return {"queued": len(responses), "total": len(_queue)}


@app.post("/admin/reset")
async def reset_queue():
    async with _lock:
        _queue.clear()
    logger.info("Queue cleared")
    return {"status": "ok"}


@app.get("/admin/status")
async def queue_status():
    return {"queue_length": len(_queue)}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/models")
async def list_models():
    """Minimal OpenAI-compatible /models endpoint to avoid 404 warnings."""
    return {
        "object": "list",
        "data": [
            {"id": "openai/gpt-4o",      "object": "model", "created": 0, "owned_by": "mock"},
            {"id": "openai/gpt-4-turbo", "object": "model", "created": 0, "owned_by": "mock"},
        ],
    }


# ---------------------------------------------------------------------------
# OpenAI-compatible completions
# ---------------------------------------------------------------------------


def _make_id() -> str:
    return f"chatcmpl-mock-{int(time.time() * 1000) % 100000000}"


def _non_streaming_response(queued: dict, model: str) -> dict:
    content = queued.get("content")
    tool_calls = queued.get("tool_calls")

    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls

    return {
        "id": _make_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
    }


async def _sse_generator(content: str, model: str):
    """Yield SSE chunks for a streaming response."""
    chunk_size = 30
    cid = _make_id()
    ts = int(time.time())

    for i in range(0, len(content), chunk_size):
        piece = content[i : i + chunk_size]
        data = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": ts,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.003)

    final = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": ts,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    is_stream = body.get("stream", False)
    model = body.get("model", "mock-model")

    async with _lock:
        if _queue:
            queued = _queue.popleft()
        else:
            logger.warning("Queue empty — returning fallback empty response")
            queued = {"content": ""}

    logger.info(
        "Serving queued response | stream=%s | has_tool_calls=%s | remaining=%d",
        is_stream,
        bool(queued.get("tool_calls")),
        len(_queue),
    )

    if settings.RESPONSE_DELAY_MS > 0:
        await asyncio.sleep(settings.RESPONSE_DELAY_MS / 1000)

    if is_stream:
        content = queued.get("content") or ""
        return StreamingResponse(
            _sse_generator(content, model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return _non_streaming_response(queued, model)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mock LLM Server")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    logger.info("Starting mock LLM server on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
