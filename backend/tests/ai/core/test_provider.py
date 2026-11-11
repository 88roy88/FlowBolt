"""Tests for stream_chat."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import litellm
import pytest

from flow44.ai.core.provider import (
    ContextWindowExceeded,
    _handle_litellm_errors,
    _prompt_cache_kwargs,
    stream_chat,
)
from flow44.config import settings

_MESSAGES = [{"role": "user", "content": "go"}]


def _chunk(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content))])


def _fake_acompletion(count: int) -> tuple[Any, dict[str, Any]]:
    seen: dict[str, Any] = {}

    async def _stream() -> AsyncIterator[SimpleNamespace]:
        for i in range(count):
            yield _chunk(str(i))

    async def _acompletion(**kwargs: Any) -> AsyncIterator[SimpleNamespace]:
        seen.update(kwargs)
        return _stream()

    return _acompletion, seen


async def test_stream_yields_every_chunk_and_uses_the_stream_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    acompletion, seen = _fake_acompletion(count=3)
    monkeypatch.setattr(litellm, "acompletion", acompletion)

    assert [chunk async for chunk in stream_chat(_MESSAGES, "sys")] == ["0", "1", "2"]
    assert seen["timeout"] == settings.AI_STREAM_TIMEOUT
    assert seen["timeout"] != settings.AI_REQUEST_TIMEOUT


async def test_unprefixed_context_length_error_becomes_context_window_exceeded() -> None:
    error = litellm.BadRequestError("maximum context length is 600000 tokens", model="m", llm_provider="openai")

    with pytest.raises(ContextWindowExceeded):
        async with _handle_litellm_errors("m"):
            raise error


@pytest.mark.parametrize(("enabled", "expected"), [(True, {"prompt_cache_key": "p1"}), (False, {})])
def test_prompt_cache_key_follows_setting(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, expected: dict[str, Any]
) -> None:
    monkeypatch.setattr(settings, "AI_SEND_PROMPT_CACHE_KEY", enabled)
    assert _prompt_cache_kwargs({"prompt_cache_key": "p1"}) == expected
