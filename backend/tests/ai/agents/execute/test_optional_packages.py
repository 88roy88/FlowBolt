"""Tests for optional package whitelist selection."""

from __future__ import annotations

from flow44.ai.agents.execute.optional_packages import (
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

CONNECTED_ASSETS_PROMPT = """
Hey, build me a small React app for investigating connected company assets.

I want a clean dashboard where I can see a list of systems, servers, databases, APIs, and owners. Each item
should have fields like name, type, status, risk level, owner, and last activity.

The app should also have a visual map that shows how these assets are connected to each other. For example,
which API talks to which database, which service depends on another service, and which owner is responsible
for each area. I want to be able to click a node in the map and see the matching asset details.

Please make the asset list easy to work with. I should be able to sort and filter it by status, type, risk
level, and owner. When I select a row in the list, it should highlight or focus the related item in the
connection map.

Keep it simple and fast to build. I don't need a big enterprise app. Just a small working demo with fake data
is enough.

Use a few real screens only if it makes sense, like:
- Dashboard
- Asset Map
- Asset Details

Please don't over-engineer it. Keep the files and components minimal, but make the app feel useful and
interactive.
"""


def test_selected_package_names_accepts_whitelisted_dict_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "react-router-dom", "capability": "client_routing", "reason": "multi-page app"},
                {"name": "regraph", "capability": "connected_data_visualization", "reason": "network graph"},
                {"name": "made-up-router", "capability": "client_routing", "reason": "not allowed"},
            ]
        }
    )

    assert selected_package_names(decision) == ["react-router-dom", "regraph"]
    assert decision.selected_packages[0].capability == "client_routing"


def test_selected_package_names_dedupes_declared_package_items() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "react-router-dom", "reason": "multi-page app"},
                {"name": "react-router-dom", "reason": "duplicate"},
            ]
        }
    )

    assert selected_package_names(decision) == ["react-router-dom"]


def test_validated_decision_preserves_first_valid_reason() -> None:
    decision = OptionalPackageDecision.model_validate(
        {
            "selected_packages": [
                {"name": "react-router-dom", "reason": "  real screens  "},
                {"name": "react-router-dom", "reason": "duplicate"},
                {"name": "unknown", "reason": "invalid"},
            ]
        }
    )

    validated = validate_optional_package_decision(decision)

    assert validated.model_dump() == {
        "selected_packages": [
            {"name": "react-router-dom", "capability": "client_routing", "reason": "real screens"},
        ]
    }


def test_optional_package_decision_defaults_missing_selection_to_empty() -> None:
    decision = OptionalPackageDecision.model_validate({})

    assert selected_package_names(decision) == []


def test_selected_package_names_accepts_legacy_package_key() -> None:
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


def test_recovered_optional_package_mappings() -> None:
    selected = ["reagraph", "react-table"]

    assert package_capabilities(selected) == ["webgl_network_graph", "interactive_data_table"]
    assert package_install_names(selected) == ["reagraph", "@tanstack/react-table"]
    assert allowed_import_names(selected) == ["reagraph", "@tanstack/react-table"]


def test_leaflet_optional_package_installs_runtime_and_types() -> None:
    selected = ["leaflet"]

    assert package_capabilities(selected) == ["interactive_geospatial_map"]
    assert package_install_names(selected) == ["leaflet", "@types/leaflet"]
    assert allowed_import_names(selected) == ["leaflet", "@types/leaflet"]


def test_connected_assets_prompt_selects_router_and_regraph() -> None:
    selected = selected_package_names(high_confidence_optional_package_decision(CONNECTED_ASSETS_PROMPT))

    assert "react-router-dom" in selected
    assert "regraph" in selected


def test_leaflet_prompt_selects_geospatial_map_package() -> None:
    selected = selected_package_names(
        high_confidence_optional_package_decision(
            "Build a Leaflet field map with latitude and longitude markers for bases."
        )
    )

    assert "leaflet" in selected


def test_selected_packages_recovered_from_actual_dependency_names() -> None:
    package_json = '{"dependencies":{"react-router-dom":"latest","@tanstack/react-table":"latest"}}'

    assert selected_packages_from_package_json(package_json) == ["react-router-dom", "react-table"]


def test_unselected_known_package_plan_reference_uses_fallback() -> None:
    repaired = repair_unselected_package_references(
        "Use react-router-dom and regraph, but keep selected reagraph.",
        ["reagraph"],
    )

    assert "react-router-dom" not in repaired
    assert "regraph," not in repaired
    assert "selected reagraph" in repaired
