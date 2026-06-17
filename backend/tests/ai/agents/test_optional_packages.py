"""Tests for optional package whitelist selection."""

from __future__ import annotations

from flow44.ai.agents.optional_packages import (
    OPTIONAL_PACKAGES,
    OptionalPackageDecision,
    OptionalPackagePrompt,
    allowed_import_names,
    has_capability,
    high_confidence_optional_package_decision,
    package_capabilities,
    package_install_names,
    render_optional_package_prompts,
    repair_unselected_package_references,
    selected_package_names,
    selected_packages_from_package_json,
    validate_optional_package_decision,
)

DATE_TIMELINE_PROMPT = "Build a project timeline with due dates and relative time labels."
FORM_VALIDATION_PROMPT = "Build a contact form with required fields and inline validation errors."
ICON_DASHBOARD_PROMPT = "Add icons to the dashboard cards and sidebar navigation."


def test_optional_package_registry_is_module_owned() -> None:
    assert list(OPTIONAL_PACKAGES) == ["lucide-react", "react-hook-form", "date-fns"]
    assert OPTIONAL_PACKAGES["lucide-react"].__class__.__module__.endswith(".lucide_react")
    assert OPTIONAL_PACKAGES["lucide-react"].packages == ("lucide-react",)


def test_package_owned_templates_render_and_skip_missing_templates() -> None:
    rendered = render_optional_package_prompts(["lucide-react"], OptionalPackagePrompt.CODEGEN_RULES)
    missing = render_optional_package_prompts(["lucide-react"], OptionalPackagePrompt.MERGE_RULES)

    assert rendered == [OPTIONAL_PACKAGES["lucide-react"].render_prompt(OptionalPackagePrompt.CODEGEN_RULES)]
    assert "Import only the icons you use from `lucide-react`" in rendered[0]
    assert missing == []


def test_selected_package_names_accepts_whitelisted_dict_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "lucide-react", "capability": "iconography", "reason": "icons requested"},
                {"name": "date-fns", "capability": "date_formatting", "reason": "date formatting"},
                {"name": "made-up-package", "capability": "unknown", "reason": "not allowed"},
            ]
        }
    )

    assert selected_package_names(decision) == ["lucide-react", "date-fns"]
    assert decision.selected_packages[0].capability == "iconography"


def test_selected_package_names_dedupes_declared_package_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "react-hook-form", "reason": "Form validation requested"},
                {"name": "react-hook-form", "reason": "duplicate"},
            ]
        }
    )

    assert selected_package_names(decision) == ["react-hook-form"]


def test_validated_decision_preserves_first_valid_reason() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "lucide-react", "reason": "  Icons requested  "},
                {"name": "lucide-react", "reason": "duplicate"},
                {"name": "unknown", "reason": "invalid"},
            ]
        }
    )

    validated = validate_optional_package_decision(decision)

    assert validated.model_dump() == {
        "selected_packages": [
            {"name": "lucide-react", "capability": "iconography", "reason": "Icons requested"},
        ]
    }


def test_optional_package_decision_defaults_missing_selection_to_empty() -> None:
    decision = OptionalPackageDecision.model_validate({})

    assert selected_package_names(decision) == []


def test_package_capability_helpers() -> None:
    selected = ["lucide-react", "react-hook-form", "date-fns"]

    assert has_capability(selected, "iconography")
    assert has_capability(selected, "form_state_validation")
    assert has_capability(selected, "date_formatting")
    assert package_capabilities(selected) == ["iconography", "form_state_validation", "date_formatting"]
    assert package_install_names(selected) == ["lucide-react", "react-hook-form", "date-fns"]


def test_recovered_optional_package_mappings() -> None:
    selected = ["date-fns"]

    assert package_capabilities(selected) == ["date_formatting"]
    assert package_install_names(selected) == ["date-fns"]
    assert allowed_import_names(selected) == ["date-fns"]


def test_icon_prompt_selects_lucide_react() -> None:
    decision = high_confidence_optional_package_decision(ICON_DASHBOARD_PROMPT)
    selected = selected_package_names(decision)

    assert selected == ["lucide-react"]


def test_form_validation_prompt_selects_react_hook_form() -> None:
    decision = high_confidence_optional_package_decision(FORM_VALIDATION_PROMPT)

    assert selected_package_names(decision) == ["react-hook-form"]


def test_date_timeline_prompt_selects_date_fns() -> None:
    selected = selected_package_names(high_confidence_optional_package_decision(DATE_TIMELINE_PROMPT))

    assert selected == ["date-fns"]


def test_selected_packages_recovered_from_actual_dependency_names() -> None:
    package_json = '{"dependencies":{"lucide-react":"latest","react-hook-form":"latest","date-fns":"latest"}}'

    assert selected_packages_from_package_json(package_json) == ["lucide-react", "react-hook-form", "date-fns"]


def test_unselected_known_package_plan_reference_uses_fallback() -> None:
    repaired = repair_unselected_package_references(
        "Use lucide-react for icons and react-hook-form for validation.",
        ["react-hook-form"],
    )

    assert "lucide-react" not in repaired
    assert "react-hook-form" in repaired
