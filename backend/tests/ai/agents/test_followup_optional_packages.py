from __future__ import annotations

from typing import Any

import pytest

import flow44.ai.agents.followup.agent as followup_agent_module
import flow44.ai.agents.optional_package_decision as optional_package_decision_module
from flow44.ai.agents.followup.agent import FollowUpAgent


class FakeSandbox:
    project_id = "project"

    def __init__(self) -> None:
        self.install_calls: list[list[str]] = []

    async def read_file(self, path: str) -> str:
        assert path == "package.json"
        return '{"dependencies":{}}'

    async def install_optional_packages(self, package_names: list[str]) -> None:
        self.install_calls.append(package_names)


@pytest.mark.asyncio
async def test_followup_decides_and_installs_optional_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = FakeSandbox()
    agent = FollowUpAgent("project", sandbox, user_id="test-user")  # type: ignore[arg-type]

    async def fake_complete_chat(
        messages: list[Any],
        system_prompt: str,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        del messages, model, metadata
        assert "## Allowed Optional Packages" in system_prompt
        return '{"selected_packages":[{"name":"mui","reason":"Material UI controls requested"}]}'

    monkeypatch.setattr(followup_agent_module.settings, "FOLLOWUP_OPTIONAL_PACKAGE_AI_DECISION_ENABLED", True)
    monkeypatch.setattr(optional_package_decision_module, "complete_chat", fake_complete_chat)

    selected = await agent._prepare_optional_packages(
        "Add Material UI controls to this dashboard.",
        {"summary": "", "file_tree": "src/App.tsx"},
    )

    assert selected == ["mui"]
    assert sandbox.install_calls == [["@mui/material", "@emotion/react", "@emotion/styled"]]


@pytest.mark.asyncio
async def test_followup_feature_flag_reuses_existing_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox = FakeSandbox()
    agent = FollowUpAgent("project", sandbox, user_id="test-user")  # type: ignore[arg-type]

    async def fail_complete_chat(*args: Any, **kwargs: Any) -> str:
        del args, kwargs
        raise AssertionError("AI package decision should be skipped")

    monkeypatch.setattr(followup_agent_module.settings, "FOLLOWUP_OPTIONAL_PACKAGE_AI_DECISION_ENABLED", False)
    monkeypatch.setattr(optional_package_decision_module, "complete_chat", fail_complete_chat)

    selected = await agent._prepare_optional_packages(
        "Add Material UI controls to this dashboard.",
        {"summary": "", "file_tree": "src/App.tsx"},
    )

    assert selected == []
    assert sandbox.install_calls == [[]]
