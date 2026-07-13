from __future__ import annotations

import importlib
import pkgutil

import flow44.ai.agents.optional_packages as _pkg
from flow44.ai.agents.optional_packages.base import OptionalPackage, OptionalPackagePrompt


def _discover() -> dict[str, OptionalPackage]:
    found: dict[str, OptionalPackage] = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        if not info.ispkg:
            continue
        module = importlib.import_module(f"{_pkg.__name__}.{info.name}")
        package = getattr(module, "PACKAGE", None)
        if isinstance(package, OptionalPackage):
            found[package.name] = package
    return dict(sorted(found.items()))


OPTIONAL_PACKAGES: dict[str, OptionalPackage] = _discover()


def validate_selection(names: list[str]) -> list[str]:
    return [name for name in dict.fromkeys(names) if name in OPTIONAL_PACKAGES]


def install_names(names: list[str]) -> list[str]:
    result: list[str] = []
    for name in names:
        package = OPTIONAL_PACKAGES.get(name)
        if package:
            result.extend(package.packages)
    return list(dict.fromkeys(result))


def optional_packages_prompt_context() -> list[dict[str, str]]:
    return [
        {"name": p.name, "capability": p.capability, "use_when": p.use_when, "avoid_when": p.avoid_when}
        for p in OPTIONAL_PACKAGES.values()
    ]


def selected_packages_context(names: list[str]) -> list[dict[str, str]]:
    context: list[dict[str, str]] = []
    for name in names:
        package = OPTIONAL_PACKAGES.get(name)
        if package:
            context.append({"name": package.name, "capability": package.capability, "use_when": package.use_when})
    return context


def render_optional_package_prompts(names: list[str], prompt: OptionalPackagePrompt) -> list[str]:
    blocks: list[str] = []
    for name in names:
        package = OPTIONAL_PACKAGES.get(name)
        if package is None:
            continue
        block = package.render_prompt(prompt)
        if block:
            blocks.append(block)
    return blocks
