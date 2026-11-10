from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.ai.agents.enhance.prompts import render_enhance
from flow44.ai.helpers import format_summary
from flow44.ai.selected_elements_context import SelectedElement, format_selected_elements
from flow44.main import app

client = TestClient(app, raise_server_exceptions=False)

PROJECT_ID = "proj-enhance"

SUMMARY = json.dumps({"summary": "A todo app", "tech_stack": ["React"], "features": ["Add todos"]})


def _mock_project(summary: str) -> MagicMock:
    project = MagicMock()
    project.id = PROJECT_ID
    project.user_id = "test-user"
    project.summary = summary
    return project


@contextmanager
def _enhance_env(*, project: MagicMock | None = None, is_new: bool = True) -> Iterator[AsyncMock]:
    complete = AsyncMock(return_value="  a fuller prompt  ")
    with (
        patch("flow44.api.deps.db_get_project", new_callable=AsyncMock, return_value=project),
        patch("flow44.api.chat.is_new_project", new_callable=AsyncMock, return_value=is_new),
        patch("flow44.ai.agents.enhance.agent.complete_chat", complete),
    ):
        yield complete


def _post(body: dict[str, Any] | None = None, *, with_project: bool = False) -> Any:
    params = {"project_id": PROJECT_ID} if with_project else None
    return client.post("/api/chat/enhance", params=params, json={"content": "a todo app", **(body or {})})


@pytest.mark.parametrize(
    ("with_project", "is_new", "summary", "expected_new"),
    [
        (False, True, "", True),
        (True, True, "", True),
        (True, False, SUMMARY, False),
    ],
)
def test_template_follows_project_state(with_project: bool, is_new: bool, summary: str, expected_new: bool) -> None:
    project = _mock_project(summary) if with_project else None
    with _enhance_env(project=project, is_new=is_new) as complete:
        response = _post(with_project=with_project)

    assert response.status_code == 200
    assert response.json() == {"enhanced": "a fuller prompt"}
    assert complete.await_args.args[1] == render_enhance(
        is_new_project=expected_new, project_summary=format_summary(summary), data_source_names=[]
    )


@pytest.mark.parametrize("names", [[], ["Sales Postgres", "CRM"]])
def test_data_source_names_reach_the_prompt(names: list[str]) -> None:
    with _enhance_env() as complete:
        response = _post({"data_source_names": names})

    assert response.status_code == 200
    assert complete.await_args.args[1] == render_enhance(is_new_project=True, data_source_names=names)


def test_selected_elements_reach_the_user_message() -> None:
    element = {"tag": "button", "selector": "#buy", "text": "Buy now", "classes": "btn", "components": ["Hero"]}
    with _enhance_env() as complete:
        response = _post({"selected_elements": [element]})

    assert response.status_code == 200
    user_message = complete.await_args.args[0][0]
    assert format_selected_elements([SelectedElement(**element)]) in user_message.content


def test_llm_failure_returns_502() -> None:
    with _enhance_env() as complete:
        complete.side_effect = RuntimeError("model down")
        response = _post()

    assert response.status_code == 502


def test_inaccessible_project_returns_404() -> None:
    with _enhance_env(project=None) as complete:
        response = _post(with_project=True)

    assert response.status_code == 404
    assert complete.await_count == 0
