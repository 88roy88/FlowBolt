"""TDD: Model mock must expose OpenAI-compatible /v1/chat/completions."""
from __future__ import annotations

from fastapi.testclient import TestClient

from mocks.model_mock.app import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_completions_returns_choices_with_content() -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "test",
            "messages": [{"role": "user", "content": "Generate a bar chart"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data
    assert len(data["choices"]) >= 1
    assert data["choices"][0].get("message", {}).get("content")
    assert "usage" in data
    assert data["usage"]["total_tokens"] >= 0


def test_chat_completions_content_is_html_like() -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "x", "messages": [{"role": "user", "content": "Chart"}]},
    )
    assert resp.status_code == 200
    content = resp.json()["choices"][0]["message"]["content"]
    assert "<html" in content.lower() or "<!DOCTYPE" in content
    assert "window.data" in content or "body" in content.lower()


def test_chat_completions_invalid_body_returns_400() -> None:
    resp = client.post("/v1/chat/completions", content="not json")
    assert resp.status_code == 400


def test_legacy_completions_returns_choices_with_text() -> None:
    resp = client.post(
        "/v1/completions",
        json={"model": "test", "prompt": "Generate HTML"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "text_completion"
    assert len(data["choices"]) >= 1
    assert isinstance(data["choices"][0].get("text"), str)
