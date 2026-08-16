from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from flow44.ai.agents import optional_packages as op
from flow44.ai.agents.execute.prompts import render_codegen, render_feedback, render_merge
from flow44.ai.agents.fix_error.agent import FixErrorAgent
from flow44.ai.agents.fix_error.prompts import render_feedback as render_fix_feedback
from flow44.ai.agents.fix_error.prompts import render_fix_error_direct
from flow44.ai.agents.followup.prompts import render_followup
from flow44.ai.agents.optional_packages import (
    OPTIONAL_PACKAGES,
    OptionalPackage,
    PackageRuleset,
    installed_packages,
    npm_dependencies,
    packages_by_name,
    render_package_rules,
    validate_selection,
)
from flow44.ai.agents.optional_packages import registry as op_registry
from flow44.ai.agents.plan import agent as plan_agent
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.agents.plan.prompts import render_package_decision
from flow44.ai.state import BuildState

SEED = {"date-fns", "lucide-react", "react-hook-form", "recharts"}

_NO_TEMPLATE_PACKAGE = OptionalPackage(
    name="no-template",
    capability="none",
    packages=("no-template",),
    templates_dir=Path(__file__).parent / "does-not-exist",
    use_when="never",
    avoid_when="always",
)


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
        assert _NO_TEMPLATE_PACKAGE.render_prompt(PackageRuleset.CODEGEN) is None

    def test_every_package_ships_every_ruleset(self) -> None:
        for pkg in OPTIONAL_PACKAGES.values():
            for ruleset in PackageRuleset:
                block = pkg.render_prompt(ruleset)
                assert block, f"{pkg.name} is missing {ruleset.value}.md"

    def test_every_fragment_starts_with_an_attributing_heading(self) -> None:
        # Blocks from several packages get concatenated; each must name its own package.
        for pkg in OPTIONAL_PACKAGES.values():
            for ruleset in PackageRuleset:
                block = pkg.render_prompt(ruleset) or ""
                assert block.startswith(f"### {pkg.name} — "), f"{pkg.name}/{ruleset.value}.md"

    def test_followup_fragments_carry_no_code_fence(self) -> None:
        # The follow-up agent reads the app's real usage; a sample would get copied instead.
        for pkg in OPTIONAL_PACKAGES.values():
            assert "```" not in (pkg.render_prompt(PackageRuleset.FOLLOWUP) or "")

    def test_recharts_codegen_mentions_responsive_container(self) -> None:
        blocks = render_package_rules(["recharts"], PackageRuleset.CODEGEN)
        assert len(blocks) == 1
        assert "ResponsiveContainer" in blocks[0]

    def test_every_codegen_fragment_is_example_first(self) -> None:
        for name in SEED:
            blocks = render_package_rules([name], PackageRuleset.CODEGEN)
            assert blocks and "import {" in blocks[0]


class TestInstalledPackages:
    def test_maps_dependencies_back_to_packages(self) -> None:
        deps = {"react": "^18", "react-dom": "^18", "recharts": "^2", "date-fns": "^3"}
        assert [p.name for p in installed_packages(deps)] == ["date-fns", "recharts"]

    def test_ignores_unrelated_deps(self) -> None:
        # The base template ships these; none is an optional package.
        assert installed_packages({"jose": "^5", "react": "^18", "react-dom": "^18"}) == []

    def test_empty_dependencies(self) -> None:
        assert installed_packages({}) == []

    def test_requires_every_npm_dep_of_a_package(self) -> None:
        multi = OptionalPackage(
            name="multi",
            capability="none",
            packages=("alpha", "beta"),
            templates_dir=Path(__file__).parent,
            use_when="",
            avoid_when="",
        )
        assert not {"alpha"} >= set(multi.packages)
        assert {"alpha", "beta"} >= set(multi.packages)


class TestDiscovery:
    def test_resolve_returns_package_for_real_module(self) -> None:
        pkg = op_registry._resolve_module_package("flow44.ai.agents.optional_packages.recharts")
        assert pkg is not None and pkg.name == "recharts"

    def test_resolve_returns_none_without_valid_package(self) -> None:
        # A module that exists but declares no PACKAGE attribute.
        assert op_registry._resolve_module_package("flow44.ai.agents.optional_packages.base") is None

    def test_discover_warns_and_keeps_the_rest(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        real = op_registry._resolve_module_package

        def _flaky(module_name: str) -> OptionalPackage | None:
            return None if module_name.endswith("recharts") else real(module_name)

        monkeypatch.setattr(op_registry, "_resolve_module_package", _flaky)
        with caplog.at_level("WARNING"):
            found = op_registry._discover()

        assert "recharts" not in found
        assert set(found) >= SEED - {"recharts"}
        assert sum("recharts" in r.message for r in caplog.records) == 1


class TestPromptInjection:
    def test_package_decision_lists_all_packages(self) -> None:
        prompt = render_package_decision()
        for name in SEED:
            assert name in prompt

    def test_decision_prompt_guards_over_selection_and_has_no_followup(self) -> None:
        prompt = render_package_decision()
        assert "zero is a common, correct answer" in prompt
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


class TestPostBuildPromptInjection:
    """The follow-up and fix-error agents must state the app's real dependency set."""

    def test_followup_lists_installed_and_injects_rules(self) -> None:
        prompt = render_followup(project_summary="s", file_tree="src/App.tsx", installed_packages=["recharts"])
        assert "`recharts`" in prompt
        assert "Package usage rules" in prompt
        assert "ResponsiveContainer" in prompt
        assert "date-fns" not in prompt

    def test_followup_without_packages_keeps_strict_rule(self) -> None:
        prompt = render_followup(project_summary="s", file_tree="src/App.tsx")
        assert "no axios, lodash" in prompt
        assert "Package usage rules" not in prompt

    def test_followup_renders_file_safety_once(self) -> None:
        prompt = render_followup(project_summary="s", file_tree="t", installed_packages=["date-fns"])
        assert prompt.count("## File Safety Rules") == 1

    def test_fix_error_direct_no_longer_forbids_an_installed_package(self) -> None:
        prompt = render_fix_error_direct(error_message="boom", files={"a.tsx": "x"}, installed_packages=["recharts"])
        assert "`recharts`" in prompt
        assert "Only use pre-installed packages" not in prompt
        assert "Package usage rules" in prompt

    def test_fix_error_direct_without_packages_keeps_strict_rule(self) -> None:
        prompt = render_fix_error_direct(error_message="boom", files={"a.tsx": "x"})
        assert "no axios, lodash" in prompt
        assert "Package usage rules" not in prompt

    def test_available_packages_block_renders_once_per_prompt(self) -> None:
        names = ["recharts"]
        assert render_followup(project_summary="s", file_tree="t", installed_packages=names).count("**CRITICAL**") == 1
        assert render_fix_error_direct(error_message="boom", files={"a.tsx": "x"}).count("**CRITICAL**") == 1
        codegen = render_codegen(
            task_title="t",
            task_description="d",
            task_files=["a.tsx"],
            architecture={},
            ux_design={},
            selected_packages=names,
        )
        assert codegen.count("**CRITICAL**") == 1

    def test_fix_error_feedback_injects_rules_only_when_present(self) -> None:
        with_rules = render_fix_feedback(files={"a.tsx": "x"}, installed_packages=["date-fns"])
        assert "Package usage rules" in with_rules
        assert "date-fns" in with_rules
        assert "Package usage rules" not in render_fix_feedback(files={"a.tsx": "x"})


class _ManifestSandbox:
    """Duck-typed sandbox returning a canned package.json (or raising)."""

    def __init__(self, payload: str | Exception) -> None:
        self._payload = payload

    async def read_file(self, path: str) -> str:
        assert path == "package.json"
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _chat_agent(payload: str | Exception) -> FixErrorAgent:
    agent = FixErrorAgent.__new__(FixErrorAgent)
    agent.sandbox = _ManifestSandbox(payload)  # type: ignore[assignment]
    agent.project_id = "p"
    return agent


class TestInstalledOptionalPackagesHelper:
    async def test_reads_dependencies_and_dev_dependencies(self) -> None:
        manifest: dict[str, Any] = {
            "dependencies": {"react": "^18", "recharts": "^2"},
            "devDependencies": {"lucide-react": "^0.3", "typescript": "^5"},
        }
        agent = _chat_agent(json.dumps(manifest))
        assert await agent._installed_optional_package_names() == ["lucide-react", "recharts"]

    async def test_missing_manifest_returns_empty(self) -> None:
        agent = _chat_agent(FileNotFoundError("package.json"))
        assert await agent._installed_optional_package_names() == []

    async def test_malformed_json_returns_empty(self) -> None:
        agent = _chat_agent("{not json")
        assert await agent._installed_optional_package_names() == []

    async def test_non_object_manifest_returns_empty(self) -> None:
        agent = _chat_agent("[1, 2, 3]")
        assert await agent._installed_optional_package_names() == []

    async def test_non_mapping_dependencies_returns_empty(self) -> None:
        agent = _chat_agent(json.dumps({"dependencies": ["recharts"]}))
        assert await agent._installed_optional_package_names() == []

    async def test_manifest_without_dependencies_returns_empty(self) -> None:
        agent = _chat_agent(json.dumps({"name": "project"}))
        assert await agent._installed_optional_package_names() == []


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


def test_packages_by_name_filters_unknown() -> None:
    assert [p.name for p in packages_by_name(["date-fns", "bogus"])] == ["date-fns"]


def test_packages_by_name_dedupes() -> None:
    assert [p.name for p in packages_by_name(["date-fns", "date-fns"])] == ["date-fns"]


def test_build_state_roundtrips_selection() -> None:
    bs = BuildState(project_id="p", selected_packages=["date-fns"])
    restored = BuildState.model_validate_json(bs.model_dump_json())
    assert restored.selected_packages == ["date-fns"]


def test_public_api_exports() -> None:
    assert hasattr(op, "OPTIONAL_PACKAGES")
