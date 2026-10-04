"""Tests for stream_chat."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import litellm
import pytest

from flow44.ai.core.provider import stream_chat
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
