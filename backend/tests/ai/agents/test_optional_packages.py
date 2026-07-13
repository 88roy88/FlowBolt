"""Tests for the optional-packages registry, prompt injection, and selection step."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from flow44.ai.agents import optional_packages as op
from flow44.ai.agents.execute.prompts import render_codegen, render_fix_errors, render_merge
from flow44.ai.agents.optional_packages import (
    OPTIONAL_PACKAGES,
    OptionalPackage,
    OptionalPackagePrompt,
    SelectedOptionalPackage,
    install_names,
    optional_packages_prompt_context,
    render_optional_package_prompts,
    selected_packages_context,
    validate_selection,
)
from flow44.ai.agents.plan import agent as plan_agent
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.agents.plan.prompts import render_package_decision
from flow44.ai.state import BuildState
from flow44.config import settings

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

    def test_install_names_flattens_and_dedupes(self) -> None:
        assert install_names(["react-hook-form", "lucide-react"]) == ["react-hook-form", "lucide-react"]
        assert install_names(["bogus"]) == []

    def test_dropped_names_are_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            validate_selection(["date-fns", "bogus"])
            install_names(["bogus"])
        assert sum("bogus" in r.message for r in caplog.records) == 2

    def test_valid_names_do_not_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            validate_selection(["date-fns"])
            install_names(["date-fns"])
        assert caplog.records == []

    def test_render_returns_blocks(self) -> None:
        blocks = render_optional_package_prompts(["date-fns"], OptionalPackagePrompt.CODEGEN_RULES)
        assert len(blocks) == 1 and "date-fns" in blocks[0]

    def test_missing_template_is_skipped_not_error(self) -> None:
        # A package that ships no templates dir -> render_prompt returns None, not an error.
        assert _NoTemplatePackage().render_prompt(OptionalPackagePrompt.CODEGEN_RULES) is None

    def test_prompt_context_shape(self) -> None:
        ctx = optional_packages_prompt_context()
        assert {"name", "capability", "use_when", "avoid_when"} == set(ctx[0])

    def test_recharts_codegen_mentions_responsive_container(self) -> None:
        blocks = render_optional_package_prompts(["recharts"], OptionalPackagePrompt.CODEGEN_RULES)
        assert len(blocks) == 1
        assert "ResponsiveContainer" in blocks[0]

    def test_every_codegen_fragment_is_example_first(self) -> None:
        for name in SEED:
            blocks = render_optional_package_prompts([name], OptionalPackagePrompt.CODEGEN_RULES)
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
        blocks = render_optional_package_prompts(names, OptionalPackagePrompt.CODEGEN_RULES)
        prompt = render_codegen(
            task_title="t",
            task_description="d",
            task_files=["a.tsx"],
            architecture={},
            ux_design={},
            allowed_packages=names,
            package_rules=blocks,
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
        with_pkgs = render_merge(
            allowed_packages=names,
            package_rules=render_optional_package_prompts(names, OptionalPackagePrompt.MERGE_RULES),
        )
        assert "lucide-react" in with_pkgs and "Package usage rules" in with_pkgs
        assert "only the pre-configured" in render_merge()

    def test_fix_errors_injects_rules_only_when_present(self) -> None:
        names = ["react-hook-form"]
        with_rules = render_fix_errors(
            errors="E",
            files={"a.tsx": "x"},
            package_rules=render_optional_package_prompts(names, OptionalPackagePrompt.FIX_ERRORS_RULES),
        )
        assert "Package usage rules" in with_rules
        assert "Package usage rules" not in render_fix_errors(errors="E", files={})


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

        monkeypatch.setattr(settings, "PLAN_OPTIONAL_PACKAGES_ENABLED", True)
        monkeypatch.setattr(plan_agent, "complete_chat", _fake_complete)

        agent = _make_agent()
        state = _plan_state(agent, "an app with a due-date timeline")
        await agent._step_decide_packages(state)

        assert state.build_state.selected_packages == [SelectedOptionalPackage(name="date-fns", reason="timeline")]

    async def test_flag_off_skips_selection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = False

        async def _fake_complete(*_a: object, **_kw: object) -> str:
            nonlocal called
            called = True
            return '{"selected": []}'

        monkeypatch.setattr(settings, "PLAN_OPTIONAL_PACKAGES_ENABLED", False)
        monkeypatch.setattr(plan_agent, "complete_chat", _fake_complete)

        agent = _make_agent()
        state = _plan_state(agent, "any request")
        await agent._step_decide_packages(state)

        assert state.build_state.selected_packages == []
        assert called is False

    async def test_llm_failure_falls_back_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _boom(*_a: object, **_kw: object) -> str:
            raise RuntimeError("llm down")

        monkeypatch.setattr(settings, "PLAN_OPTIONAL_PACKAGES_ENABLED", True)
        monkeypatch.setattr(plan_agent, "complete_chat", _boom)

        agent = _make_agent()
        state = _plan_state(agent, "any request")
        await agent._step_decide_packages(state)

        assert state.build_state.selected_packages == []


def test_selected_packages_context_filters_unknown() -> None:
    ctx = selected_packages_context(["date-fns", "bogus"])
    assert [c["name"] for c in ctx] == ["date-fns"]


def test_build_state_roundtrips_selection() -> None:
    bs = BuildState(project_id="p", selected_packages=[SelectedOptionalPackage(name="date-fns", reason="r")])
    restored = BuildState.model_validate_json(bs.model_dump_json())
    assert restored.selected_packages == [SelectedOptionalPackage(name="date-fns", reason="r")]


def test_public_api_exports() -> None:
    assert hasattr(op, "OPTIONAL_PACKAGES")
