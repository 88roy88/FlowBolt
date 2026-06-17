from __future__ import annotations

from typing import Any

import pytest

import flow44.ai.agents.optional_package_decision as optional_package_decision_module
import flow44.ai.agents.plan.agent as plan_agent_module
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.state import BuildState
from tests.ai.agents.test_optional_packages import DATE_TIMELINE_PROMPT


@pytest.mark.asyncio
async def test_plan_agent_decides_optional_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    build_state = BuildState(project_id="project", user_content=DATE_TIMELINE_PROMPT)
    state = PlanState(
        build_state=build_state,
        project_id="project",
        model="model",
        llm_metadata_fn=lambda _: {},
    )
    agent = PlanAgent.__new__(PlanAgent)

    async def fake_complete_chat(
        messages: list[Any],
        system_prompt: str,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        del messages, model, metadata
        assert "## Allowed Optional Packages" in system_prompt
        return '{"selected_packages":[]}'

    monkeypatch.setattr(plan_agent_module.settings, "PLAN_OPTIONAL_PACKAGE_AI_DECISION_ENABLED", True)
    monkeypatch.setattr(optional_package_decision_module, "complete_chat", fake_complete_chat)

    await PlanAgent._step_decide_optional_packages(agent, state)

    assert state.build_state.optional_package_decision is not None
    assert [pkg.name for pkg in state.build_state.optional_package_decision.selected_packages] == ["date-fns"]


@pytest.mark.asyncio
async def test_plan_agent_feature_flag_skips_ai_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    build_state = BuildState(project_id="project", user_content=DATE_TIMELINE_PROMPT)
    state = PlanState(
        build_state=build_state,
        project_id="project",
        model="model",
        llm_metadata_fn=lambda _: {},
    )
    agent = PlanAgent.__new__(PlanAgent)

    async def fail_complete_chat(*args: Any, **kwargs: Any) -> str:
        del args, kwargs
        raise AssertionError("AI package decision should be skipped")

    monkeypatch.setattr(plan_agent_module.settings, "PLAN_OPTIONAL_PACKAGE_AI_DECISION_ENABLED", False)
    monkeypatch.setattr(optional_package_decision_module, "complete_chat", fail_complete_chat)

    await PlanAgent._step_decide_optional_packages(agent, state)

    assert state.build_state.optional_package_decision is not None
    assert [pkg.name for pkg in state.build_state.optional_package_decision.selected_packages] == ["date-fns"]
