from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Iterable

import flow44.ai.agents.optional_packages as _pkg
from flow44.ai.agents.optional_packages.base import OptionalPackage, PackageRuleset

logger = logging.getLogger(__name__)


def _resolve_module_package(module_name: str) -> OptionalPackage | None:
    module = importlib.import_module(module_name)
    package = getattr(module, "PACKAGE", None)
    return package if isinstance(package, OptionalPackage) else None


def _discover() -> dict[str, OptionalPackage]:
    found: dict[str, OptionalPackage] = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        if not info.ispkg:
            continue
        package = _resolve_module_package(f"{_pkg.__name__}.{info.name}")
        if package is None:
            logger.warning("Skipping optional-package directory with no valid PACKAGE: %s", info.name)
            continue
        found[package.name] = package
    return dict(sorted(found.items()))


OPTIONAL_PACKAGES: dict[str, OptionalPackage] = _discover()


def validate_selection(names: list[str]) -> list[str]:
    unique = list(dict.fromkeys(names))
    dropped = [name for name in unique if name not in OPTIONAL_PACKAGES]
    if dropped:
        logger.warning("Dropping off-list package selection: %s", dropped)
    return [name for name in unique if name in OPTIONAL_PACKAGES]


def packages_by_name(names: list[str]) -> list[OptionalPackage]:
    unique = list(dict.fromkeys(names))
    return [package for name in unique if (package := OPTIONAL_PACKAGES.get(name))]


def installed_packages(dependencies: Iterable[str]) -> list[OptionalPackage]:
    present = set(dependencies)
    return [pkg for pkg in OPTIONAL_PACKAGES.values() if present.issuperset(pkg.packages)]


def npm_dependencies(names: list[str]) -> list[str]:
    result = [pkg for package in packages_by_name(names) for pkg in package.packages]
    return list(dict.fromkeys(result))


def render_package_rules(names: list[str], prompt: PackageRuleset) -> list[str]:
    return [block for package in packages_by_name(names) if (block := package.render_prompt(prompt))]
