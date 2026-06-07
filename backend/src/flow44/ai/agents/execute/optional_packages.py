"""Whitelisted optional npm packages for generated apps."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


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
    when_to_use: str
    when_not_to_use: str
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
        when_to_use="Use for true multi-page client-side apps with route navigation.",
        when_not_to_use="Do not use for tabs, dashboards, landing pages, or in-page sections.",
    ),
    "regraph": OptionalPackage(
        name="regraph",
        capability="connected_data_visualization",
        packages=("regraph",),
        when_to_use=(
            "Use for interactive connected-data visualizations such as networks, entity relationship graphs, "
            "dependency maps, investigation graphs, or timelines over graph items."
        ),
        when_not_to_use=(
            "Do not use for ordinary charts, static diagrams, tree views, flowcharts, org charts, tables, "
            "or small relationship summaries that can be built with React and CSS."
        ),
    ),
}


class SelectedOptionalPackage(BaseModel):
    package: str
    capability: str = ""
    reason: str = ""


class OptionalPackageDecision(BaseModel):
    selected_packages: list[SelectedOptionalPackage] = Field(default_factory=list)


def optional_package_prompt_context() -> list[dict[str, str]]:
    return [
        {
            "name": package.name,
            "capability": package.capability,
            "when_to_use": package.when_to_use,
            "when_not_to_use": package.when_not_to_use,
        }
        for package in OPTIONAL_PACKAGES.values()
    ]


def selected_package_names(decision: OptionalPackageDecision) -> list[str]:
    """Extract package names from model output and keep only whitelisted packages."""
    return validate_optional_packages([item.package for item in decision.selected_packages])


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
    for name in validate_optional_packages(package_names):
        packages.extend(OPTIONAL_PACKAGES[name].packages)
    return packages


def has_capability(package_names: list[str], capability: str) -> bool:
    return any(OPTIONAL_PACKAGES[name].capability == capability for name in validate_optional_packages(package_names))


def package_capabilities(package_names: list[str]) -> list[str]:
    return [OPTIONAL_PACKAGES[name].capability for name in validate_optional_packages(package_names)]
