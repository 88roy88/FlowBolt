from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from flow44.api.deps import get_user_permissions
from flow44.auth.permissions import Permission
from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)

PROJECT_ID = "proj-enhance"

SUMMARY = json.dumps({"summary": "A todo app", "tech_stack": ["React"], "features": ["Add todos"]})


def _mock_project(summary: str = "") -> MagicMock:
    project = MagicMock()
    project.id = PROJECT_ID
    project.user_id = "user-a"
    project.summary = summary
    return project


@contextmanager
def _enhance_env(*, is_new: bool, summary: str = "") -> Iterator[AsyncMock]:
    complete = AsyncMock(return_value="  a fuller prompt  ")
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=_mock_project(summary)),
        patch("flow44.api.deps.get_project_member", new_callable=AsyncMock, return_value=object()),
        patch("flow44.api.deps.get_user_id", return_value="user-a"),
        patch("flow44.api.chat._is_new_project", new_callable=AsyncMock, return_value=is_new),
        patch("flow44.ai.agents.enhance.agent.complete_chat", complete),
    ):
        yield complete


def _post(body: dict[str, Any] | None = None) -> Any:
    return client.post(f"/api/chat/{PROJECT_ID}/enhance", json={"content": "a todo app", **(body or {})})


def _system_prompt(complete: AsyncMock) -> str:
    return complete.await_args.args[1]


def test_new_project_uses_expansion_template() -> None:
    with _enhance_env(is_new=True) as complete:
        response = _post()

    assert response.status_code == 200
    assert response.json() == {"enhanced": "a fuller prompt"}
    prompt = _system_prompt(complete)
    assert "Look & feel" in prompt
    assert "The app today" not in prompt


def test_followup_uses_scoping_template_with_summary() -> None:
    with _enhance_env(is_new=False, summary=SUMMARY) as complete:
        response = _post({"content": "make the header sticky"})

    assert response.status_code == 200
    prompt = _system_prompt(complete)
    assert "The app today" in prompt
    assert "A todo app" in prompt
    assert "Look & feel" not in prompt


def test_followup_with_empty_summary_still_enhances() -> None:
    with _enhance_env(is_new=False) as complete:
        response = _post({"content": "make the header sticky"})

    assert response.status_code == 200
    assert "The app today" in _system_prompt(complete)


def test_data_source_names_reach_the_prompt() -> None:
    with _enhance_env(is_new=True) as complete:
        response = _post({"data_source_names": ["Sales Postgres", "CRM"]})

    assert response.status_code == 200
    prompt = _system_prompt(complete)
    assert "Sales Postgres, CRM" in prompt
    assert "Never invent fields" in prompt


def test_prompt_omits_the_data_source_block_when_none_are_attached() -> None:
    with _enhance_env(is_new=True) as complete:
        response = _post()

    assert response.status_code == 200
    assert "Never invent fields" not in _system_prompt(complete)


def test_model_is_passed_through() -> None:
    with _enhance_env(is_new=True) as complete:
        _post({"model": "some/model"})

    assert complete.await_args.kwargs["model"] == "some/model"


def test_metadata_is_opik_shaped() -> None:
    with _enhance_env(is_new=True) as complete:
        _post()

    metadata = complete.await_args.kwargs["metadata"]
    assert metadata["opik"]["generation_name"] == "enhance_prompt"


def test_llm_failure_returns_502() -> None:
    with _enhance_env(is_new=True) as complete:
        complete.side_effect = RuntimeError("model down")
        response = _post()

    assert response.status_code == 502


def test_requires_write_permission() -> None:
    app.dependency_overrides[get_user_permissions] = lambda: {Permission.read}
    try:
        with _enhance_env(is_new=True) as complete:
            response = _post()
        assert response.status_code == 403
        assert complete.await_count == 0
    finally:
        app.dependency_overrides.pop(get_user_permissions, None)


def test_empty_content_is_rejected() -> None:
    with _enhance_env(is_new=True) as complete:
        response = client.post(f"/api/chat/{PROJECT_ID}/enhance", json={"content": ""})

    assert response.status_code == 422
    assert complete.await_count == 0
