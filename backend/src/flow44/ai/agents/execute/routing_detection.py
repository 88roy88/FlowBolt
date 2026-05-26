"""Detect when a generated app needs client-side routing."""

from __future__ import annotations


def _collect_paths(plan_data: dict, architecture_file_structure: list[str] | None) -> list[str]:
    paths: list[str] = []
    for task in plan_data.get("tasks", []):
        paths.extend(task.get("files", []))
    if architecture_file_structure:
        paths.extend(architecture_file_structure)
    return paths


def detect_uses_routing(
    user_content: str,
    plan_data: dict,
    *,
    architecture_file_structure: list[str] | None = None,
) -> bool:
    """Return True when the app should install react-router-dom."""
    del user_content  # merge plan + file structure are the source of truth
    if plan_data.get("uses_routing"):
        return True
    return any(path.startswith("src/pages/") for path in _collect_paths(plan_data, architecture_file_structure))
