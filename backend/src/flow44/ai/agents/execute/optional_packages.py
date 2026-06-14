"""Whitelisted optional npm packages for generated apps."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class OptionalPackagePrompt(StrEnum):
    CODEGEN_CONTEXT = "codegen_context"
    CODEGEN_RULES = "codegen_rules"
    CODEGEN_UNSELECTED_RULES = "codegen_unselected_rules"
    MERGE_RULES = "merge_rules"
    MERGE_UNSELECTED_RULES = "merge_unselected_rules"
    FIX_ERRORS_RULES = "fix_errors_rules"
    FIX_ERRORS_UNSELECTED_RULES = "fix_errors_unselected_rules"


@dataclass(frozen=True)
class OptionalPackage:
    name: str
    capability: str
    packages: tuple[str, ...]
    use_when: str
    avoid_when: str
    strong_intent_groups: tuple[tuple[str, ...], ...] = ()
    template_dir: str | None = None

    @property
    def prompt_dir(self) -> str:
        return self.template_dir or self.name

    def prompt_template(self, prompt: OptionalPackagePrompt) -> str:
        return f"optional_packages/{self.prompt_dir}/{prompt.value}.jinja2"


OPTIONAL_PACKAGES: dict[str, OptionalPackage] = {
    "react-router-dom": OptionalPackage(
        name="react-router-dom",
        capability="client_routing",
        packages=("react-router-dom",),
        use_when=(
            "Use when the user asks for multiple real screens/pages, route URLs, deep links, nested routes, "
            "or browser back/forward behavior."
        ),
        avoid_when=(
            "Avoid for one-screen apps, simple tabs, accordions, same-page sections, or local conditional "
            "panels that do not need URLs."
        ),
        strong_intent_groups=(("deep link",), ("browser back",), ("route url",)),
    ),
    "mui": OptionalPackage(
        name="mui",
        capability="material_ui_components",
        packages=("@mui/material", "@emotion/react", "@emotion/styled"),
        use_when=(
            "Use when the user explicitly asks for Material UI or MUI, or when the app needs a broad set of "
            "polished Material Design controls such as dialogs, menus, drawers, data-entry controls, and "
            "consistent accessible components."
        ),
        avoid_when=(
            "Avoid when Tailwind and basic React components are sufficient, when the user asks for another "
            "design system, or when Material Design would conflict with the requested visual style."
        ),
        strong_intent_groups=(("material ui",), ("mui",)),
    ),
    "recharts": OptionalPackage(
        name="recharts",
        capability="dashboard_charts",
        packages=("recharts",),
        use_when=(
            "Use when the user requests dashboard charts, data visualization, trends, comparisons, "
            "time-series charts, bar charts, line charts, area charts, or pie charts."
        ),
        avoid_when=(
            "Do not use for maps, relationship graphs, node-edge diagrams, plain numeric KPI cards, "
            "or data that is clearer as a simple table or list."
        ),
        strong_intent_groups=(
            ("chart",),
            ("data visualization",),
            ("time series",),
            ("trend", "graph"),
            ("dashboard", "chart"),
        ),
    ),
}


class SelectedOptionalPackage(BaseModel):
    name: str
    capability: str = ""
    reason: str = ""

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_package_key(cls, data: dict[str, object]) -> dict[str, object]:
        if "name" not in data and "package" in data:
            return data | {"name": data["package"]}
        return data


class OptionalPackageDecision(BaseModel):
    selected_packages: list[SelectedOptionalPackage] = Field(default_factory=list)


def optional_package_prompt_context() -> list[dict[str, str]]:
    return [
        {
            "name": package.name,
            "capability": package.capability,
            "use_when": package.use_when,
            "avoid_when": package.avoid_when,
        }
        for package in OPTIONAL_PACKAGES.values()
    ]


def validate_optional_package_decision(decision: OptionalPackageDecision) -> OptionalPackageDecision:
    """Canonicalize model output, preserving the first valid reason for each selected package."""
    selected: list[SelectedOptionalPackage] = []
    seen: set[str] = set()
    for item in decision.selected_packages:
        if item.name not in OPTIONAL_PACKAGES or item.name in seen:
            continue
        package = OPTIONAL_PACKAGES[item.name]
        selected.append(
            SelectedOptionalPackage(
                name=package.name,
                capability=package.capability,
                reason=item.reason.strip(),
            )
        )
        seen.add(item.name)
    return OptionalPackageDecision(selected_packages=selected)


def high_confidence_optional_package_decision(user_request: str) -> OptionalPackageDecision:
    """Select packages for explicit, high-confidence registry-owned intent signals."""
    normalized_request = user_request.casefold()
    selected = [
        SelectedOptionalPackage(
            name=package.name,
            capability=package.capability,
            reason=f"Explicit request matches the {package.capability} capability.",
        )
        for package in OPTIONAL_PACKAGES.values()
        if any(
            all(signal.casefold() in normalized_request for signal in group) for group in package.strong_intent_groups
        )
    ]
    return OptionalPackageDecision(selected_packages=selected)


def merge_optional_package_decisions(*decisions: OptionalPackageDecision) -> OptionalPackageDecision:
    """Merge decisions in priority order, preserving first valid reasons and deduplicating names."""
    return validate_optional_package_decision(
        OptionalPackageDecision(
            selected_packages=[item for decision in decisions for item in decision.selected_packages]
        )
    )


def selected_package_names(decision: OptionalPackageDecision) -> list[str]:
    """Extract package names from model output and keep only whitelisted packages."""
    return [item.name for item in validate_optional_package_decision(decision).selected_packages]


def validate_optional_packages(package_names: list[str]) -> list[str]:
    """Return unique whitelisted package names in selection order."""
    selected: list[str] = []
    seen: set[str] = set()
    for name in package_names:
        if name not in OPTIONAL_PACKAGES or name in seen:
            continue
        selected.append(name)
        seen.add(name)
    return selected


def package_install_names(package_names: list[str]) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for name in validate_optional_packages(package_names):
        for package_name in OPTIONAL_PACKAGES[name].packages:
            if package_name in seen:
                continue
            packages.append(package_name)
            seen.add(package_name)
    return packages


def allowed_import_names(package_names: list[str]) -> list[str]:
    """Return the external import specifiers made available by selected packages."""
    return package_install_names(package_names)


def selected_packages_from_package_json(package_json: str) -> list[str]:
    """Recover selected whitelisted packages from installed dependency declarations."""
    import json  # noqa: PLC0415

    try:
        parsed = json.loads(package_json)
    except (json.JSONDecodeError, TypeError):
        return []
    dependencies = parsed.get("dependencies", {})
    if not isinstance(dependencies, dict):
        return []
    return [
        name
        for name, package in OPTIONAL_PACKAGES.items()
        if all(package_name in dependencies for package_name in package.packages)
    ]


def repair_unselected_package_references(text: str, selected_packages: list[str]) -> str:
    """Replace known unselected optional-package plan references with a browser fallback."""
    selected = set(validate_optional_packages(selected_packages))
    repaired = text
    for name, package in OPTIONAL_PACKAGES.items():
        if name in selected:
            continue
        for reference in {name, *package.packages}:
            repaired = re.sub(re.escape(reference), "React/browser fallback", repaired, flags=re.IGNORECASE)
    return repaired


def has_capability(package_names: list[str], capability: str) -> bool:
    return any(OPTIONAL_PACKAGES[name].capability == capability for name in validate_optional_packages(package_names))


def package_capabilities(package_names: list[str]) -> list[str]:
    return [OPTIONAL_PACKAGES[name].capability for name in validate_optional_packages(package_names)]
