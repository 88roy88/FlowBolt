"""Tests for the optional-packages registry, prompt injection, and selection step."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from flow44.ai.agents import optional_packages as op
from flow44.ai.agents.execute.prompts import render_codegen, render_feedback, render_merge
from flow44.ai.agents.optional_packages import (
    OPTIONAL_PACKAGES,
    OptionalPackage,
    PackageRuleset,
    npm_dependencies,
    render_package_rules,
    resolve_packages,
    validate_selection,
)
from flow44.ai.agents.plan import agent as plan_agent
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.agents.plan.prompts import render_package_decision
from flow44.ai.state import BuildState

SEED = {"date-fns", "lucide-react", "react-hook-form", "recharts"}


class _NoTemplatePackage(OptionalPackage):
    name = "no-template"
    capability = "none"
    packages = ("no-template",)
    use_when = "never"
    avoid_when = "always"


class TestRegistry:
    def test_autodiscovers_seed_packages(self) -> None:
        assert set(OPTIONAL_PACKAGES) >= SEED

    def test_every_package_declares_required_fields(self) -> None:
        for pkg in OPTIONAL_PACKAGES.values():
            assert pkg.name and pkg.capability and pkg.packages
            assert pkg.use_when and pkg.avoid_when

    def test_validate_selection_drops_unknown_and_dedupes(self) -> None:
        assert validate_selection(["date-fns", "bogus", "date-fns"]) == ["date-fns"]

    def test_npm_dependencies_flattens_and_dedupes(self) -> None:
        assert npm_dependencies(["react-hook-form", "lucide-react"]) == ["react-hook-form", "lucide-react"]
        assert npm_dependencies(["bogus"]) == []

    def test_dropped_names_are_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            validate_selection(["date-fns", "bogus"])
        assert sum("bogus" in r.message for r in caplog.records) == 1

    def test_valid_names_do_not_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            validate_selection(["date-fns"])
            npm_dependencies(["date-fns"])
        assert caplog.records == []

    def test_render_returns_blocks(self) -> None:
        blocks = render_package_rules(["date-fns"], PackageRuleset.CODEGEN)
        assert len(blocks) == 1 and "date-fns" in blocks[0]

    def test_missing_template_is_skipped_not_error(self) -> None:
        # A package that ships no templates dir -> render_prompt returns None, not an error.
        assert _NoTemplatePackage().render_prompt(PackageRuleset.CODEGEN) is None

    def test_recharts_codegen_mentions_responsive_container(self) -> None:
        blocks = render_package_rules(["recharts"], PackageRuleset.CODEGEN)
        assert len(blocks) == 1
        assert "ResponsiveContainer" in blocks[0]

    def test_every_codegen_fragment_is_example_first(self) -> None:
        for name in SEED:
            blocks = render_package_rules([name], PackageRuleset.CODEGEN)
            assert blocks and "import {" in blocks[0]


class TestPromptInjection:
    def test_package_decision_lists_all_packages(self) -> None:
        prompt = render_package_decision()
        for name in SEED:
            assert name in prompt

    def test_decision_prompt_guards_over_selection_and_has_no_followup(self) -> None:
        prompt = render_package_decision()
        assert "only because it is available" in prompt
        assert "follow-up" not in prompt.lower() and "followup" not in prompt.lower()

    def test_codegen_includes_selected_excludes_others(self) -> None:
        names = ["date-fns"]
        prompt = render_codegen(
            task_title="t",
            task_description="d",
            task_files=["a.tsx"],
            architecture={},
            ux_design={},
            selected_packages=names,
        )
        assert "Selected Package Rules" in prompt
        assert "date-fns" in prompt
        assert "react-hook-form" not in prompt

    def test_codegen_without_packages_keeps_strict_rule(self) -> None:
        prompt = render_codegen(
            task_title="t", task_description="d", task_files=["a.tsx"], architecture={}, ux_design={}
        )
        assert "no axios, lodash" in prompt
        assert "Selected Package Rules" not in prompt

    def test_merge_allow_list_vs_strict(self) -> None:
        names = ["lucide-react"]
        with_pkgs = render_merge(selected_packages=names)
        assert "lucide-react" in with_pkgs and "Package usage rules" in with_pkgs
        assert "only the pre-configured" in render_merge()

    def test_fix_errors_injects_rules_only_when_present(self) -> None:
        names = ["react-hook-form"]
        with_rules = render_feedback(files={"a.tsx": "x"}, selected_packages=names)
        assert "Package usage rules" in with_rules
        assert "Package usage rules" not in render_feedback(files={})


def _make_agent() -> plan_agent.PlanAgent:
    sandbox = SimpleNamespace(project_id="proj")
    return plan_agent.PlanAgent("proj", sandbox, user_id="u")  # type: ignore[arg-type]


def _plan_state(agent: plan_agent.PlanAgent, content: str) -> PlanState:
    agent._state.user_content = content
    return PlanState(build_state=agent._state, project_id="proj")


class TestDecidePackagesStep:
    async def test_selects_and_validates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_complete(*_a: object, **_kw: object) -> str:
            return '{"selected": [{"name": "date-fns", "reason": "timeline"}, {"name": "bogus", "reason": "x"}]}'

        monkeypatch.setattr(plan_agent, "complete_chat", _fake_complete)

        agent = _make_agent()
        state = _plan_state(agent, "an app with a due-date timeline")
        await agent._step_decide_packages(state)

        assert state.build_state.selected_packages == ["date-fns"]

    async def test_llm_failure_falls_back_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _boom(*_a: object, **_kw: object) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(plan_agent, "complete_chat", _boom)

        agent = _make_agent()
        state = _plan_state(agent, "any request")
        await agent._step_decide_packages(state)

        assert state.build_state.selected_packages == []


def test_resolve_packages_filters_unknown() -> None:
    assert [p.name for p in resolve_packages(["date-fns", "bogus"])] == ["date-fns"]


def test_resolve_packages_dedupes() -> None:
    assert [p.name for p in resolve_packages(["date-fns", "date-fns"])] == ["date-fns"]


def test_build_state_roundtrips_selection() -> None:
    bs = BuildState(project_id="p", selected_packages=["date-fns"])
    restored = BuildState.model_validate_json(bs.model_dump_json())
    assert restored.selected_packages == ["date-fns"]


def test_public_api_exports() -> None:
    assert hasattr(op, "OPTIONAL_PACKAGES")
