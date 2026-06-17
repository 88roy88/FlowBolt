"""Tests for optional package whitelist selection."""

from __future__ import annotations

from flow44.ai.agents.optional_packages import (
    OptionalPackageDecision,
    allowed_import_names,
    has_capability,
    high_confidence_optional_package_decision,
    package_capabilities,
    package_install_names,
    repair_unselected_package_references,
    selected_package_names,
    selected_packages_from_package_json,
    validate_optional_package_decision,
)

CHART_DASHBOARD_PROMPT = "Build a dashboard with line charts and bar charts showing trends over time."


def test_selected_package_names_accepts_whitelisted_dict_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "mui", "capability": "material_ui_components", "reason": "Material UI requested"},
                {"name": "recharts", "capability": "dashboard_charts", "reason": "dashboard charts"},
                {"name": "made-up-package", "capability": "unknown", "reason": "not allowed"},
            ]
        }
    )

    assert selected_package_names(decision) == ["mui", "recharts"]
    assert decision.selected_packages[0].capability == "material_ui_components"


def test_selected_package_names_dedupes_declared_package_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "mui", "reason": "Material UI requested"},
                {"name": "mui", "reason": "duplicate"},
            ]
        }
    )

    assert selected_package_names(decision) == ["mui"]


def test_validated_decision_preserves_first_valid_reason() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "mui", "reason": "  Material UI requested  "},
                {"name": "mui", "reason": "duplicate"},
                {"name": "unknown", "reason": "invalid"},
            ]
        }
    )

    validated = validate_optional_package_decision(decision)

    assert validated.model_dump() == {
        "selected_packages": [
            {"name": "mui", "capability": "material_ui_components", "reason": "Material UI requested"},
        ]
    }


def test_optional_package_decision_defaults_missing_selection_to_empty() -> None:
    decision = OptionalPackageDecision.model_validate({})

    assert selected_package_names(decision) == []


def test_package_capability_helpers() -> None:
    selected = ["mui", "recharts"]

    assert has_capability(selected, "material_ui_components")
    assert has_capability(selected, "dashboard_charts")
    assert package_capabilities(selected) == ["material_ui_components", "dashboard_charts"]
    assert package_install_names(selected) == ["@mui/material", "@emotion/react", "@emotion/styled", "recharts"]


def test_recovered_optional_package_mappings() -> None:
    selected = ["recharts"]

    assert package_capabilities(selected) == ["dashboard_charts"]
    assert package_install_names(selected) == ["recharts"]
    assert allowed_import_names(selected) == ["recharts"]


def test_explicit_mui_prompt_selects_mui() -> None:
    decision = high_confidence_optional_package_decision("Build this dashboard with Material UI.")
    selected = selected_package_names(decision)

    assert selected == ["mui"]


def test_chart_dashboard_prompt_selects_recharts() -> None:
    selected = selected_package_names(high_confidence_optional_package_decision(CHART_DASHBOARD_PROMPT))

    assert selected == ["recharts"]


def test_selected_packages_recovered_from_actual_dependency_names() -> None:
    package_json = (
        '{"dependencies":{"@mui/material":"latest","@emotion/react":"latest",'
        '"@emotion/styled":"latest","recharts":"latest"}}'
    )

    assert selected_packages_from_package_json(package_json) == ["mui", "recharts"]


def test_unselected_known_package_plan_reference_uses_fallback() -> None:
    repaired = repair_unselected_package_references(
        "Use mui for controls and recharts for dashboard charts.",
        ["recharts"],
    )

    assert "mui" not in repaired
    assert "recharts" in repaired
