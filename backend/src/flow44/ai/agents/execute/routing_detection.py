"""Detect the plan capability flag ``uses_routing`` for generated apps."""

from __future__ import annotations

from typing import Any


def _collect_paths(plan_data: dict[str, Any], architecture_file_structure: list[str] | None) -> list[str]:
    paths: list[str] = []
    for task in plan_data.get("tasks", []):
        paths.extend(task.get("files", []))
    if architecture_file_structure:
        paths.extend(architecture_file_structure)
    return paths


def detect_uses_routing(
    user_content: str,
    plan_data: dict[str, Any],
    *,
    architecture_file_structure: list[str] | None = None,
    architecture_uses_routing: bool = False,
) -> bool:
    """Return whether the AI plan marks this app as needing client-side routing.

    ``uses_routing`` is a plan capability flag only. It does not mean the backend
    implements routing — it tells the sandbox to install ``react-router-dom`` and
    tells codegen to write normal React Router code in the generated app.
    """
    del user_content  # merge plan + file structure are the source of truth
    if plan_data.get("uses_routing") or architecture_uses_routing:
        return True
    return any(path.startswith("src/pages/") for path in _collect_paths(plan_data, architecture_file_structure))
