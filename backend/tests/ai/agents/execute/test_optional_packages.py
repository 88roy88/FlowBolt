"""Tests for optional package whitelist selection."""

from __future__ import annotations

from flow44.ai.agents.execute.optional_packages import (
    OptionalPackageDecision,
    has_capability,
    package_capabilities,
    package_install_names,
    selected_package_names,
)


def test_selected_package_names_accepts_whitelisted_dict_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"package": "react-router-dom", "capability": "client_routing", "reason": "multi-page app"},
                {"package": "regraph", "capability": "connected_data_visualization", "reason": "network graph"},
                {"package": "made-up-router", "capability": "client_routing", "reason": "not allowed"},
            ]
        }
    )

    assert selected_package_names(decision) == ["react-router-dom", "regraph"]


def test_selected_package_names_dedupes_declared_package_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"package": "react-router-dom", "capability": "client_routing", "reason": "multi-page app"},
                {"package": "react-router-dom", "capability": "client_routing", "reason": "duplicate"},
            ]
        }
    )

    assert selected_package_names(decision) == ["react-router-dom"]


def test_optional_package_decision_defaults_missing_selection_to_empty() -> None:
    decision = OptionalPackageDecision.model_validate({})

    assert selected_package_names(decision) == []


def test_selected_package_names_accepts_minimal_package_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"package": "react-router-dom"},
            ]
        }
    )

    assert selected_package_names(decision) == ["react-router-dom"]


def test_package_capability_helpers() -> None:
    selected = ["react-router-dom", "regraph"]

    assert has_capability(selected, "client_routing")
    assert has_capability(selected, "connected_data_visualization")
    assert package_capabilities(selected) == ["client_routing", "connected_data_visualization"]
    assert package_install_names(selected) == ["react-router-dom", "regraph"]
