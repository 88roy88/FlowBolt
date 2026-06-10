"""Whitelisted optional npm packages for generated apps."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class OptionalPackagePrompt(StrEnum):
    CODEGEN_CONTEXT = "codegen_context"
    CODEGEN_RULES = "codegen_rules"
    MERGE_RULES = "merge_rules"
    FIX_ERRORS_RULES = "fix_errors_rules"


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
            "Use when the user asks for multiple real screens/pages; Dashboard, Details, Map, or Settings "
            "page concepts; header/sidebar navigation between screens; route URLs; deep links; nested routes; "
            "or browser back/forward behavior. A request for a few real screens such as Dashboard, Asset Map, "
            "and Asset Details should usually use routing when they naturally map to separate views."
        ),
        avoid_when=(
            "Avoid for one-screen apps, simple tabs, accordions, same-page sections, or local conditional "
            "panels that do not need URLs."
        ),
        strong_intent_groups=(("real screens",), ("deep link",), ("browser back",), ("route url",)),
    ),
    "regraph": OptionalPackage(
        name="regraph",
        capability="connected_data_visualization",
        packages=("regraph",),
        use_when=(
            "Use for interactive relationship, node/edge, network, dependency, or connection maps; assets, "
            "services, APIs, databases, or owners connected to each other; clickable nodes; highlighted "
            "connections; selecting a table row to focus a graph node; or relationship exploration. ReGraph "
            "is paid but available inside the organization, so do not avoid it because it is paid."
        ),
        avoid_when=(
            "Avoid for ordinary charts, static diagrams, simple cards, normal tables, non-interactive "
            "summaries, or a tiny static org chart that can be plain HTML/CSS."
        ),
        strong_intent_groups=(
            ("visual map", "connected"),
            ("connection map", "click"),
            ("connection map", "highlight"),
            ("click a node",),
            ("highlight", "graph node"),
        ),
    ),
    "reagraph": OptionalPackage(
        name="reagraph",
        capability="webgl_network_graph",
        packages=("reagraph",),
        use_when=(
            "Use when the user specifically needs a WebGL network graph, draggable nodes, or a force-directed "
            "or hierarchical layout over separate nodes and edges arrays."
        ),
        avoid_when=(
            "Do not use for bar/line/pie charts, static diagrams, tables, org charts drawn with CSS, "
            "Cambridge ReGraph item timelines, general connected-data investigation maps where ReGraph is the "
            "better fit, or tiny relationship summaries that do not need WebGL rendering."
        ),
    ),
    "react-table": OptionalPackage(
        name="react-table",
        capability="interactive_data_table",
        packages=("@tanstack/react-table",),
        use_when=(
            "Use for interactive tabular data with sorting, filtering, pagination, column visibility, "
            "or row selection over a dataset larger than a simple static list."
        ),
        avoid_when=(
            "Do not use for tiny static lists, card grids, key-value detail panels, or layouts that only "
            "need a plain HTML table without interactive column controls."
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
