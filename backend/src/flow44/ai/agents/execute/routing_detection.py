"""Detect when a generated app needs client-side routing."""

from __future__ import annotations

ROUTING_KEYWORDS: tuple[str, ...] = (
    "multi-page",
    "multiple pages",
    "multi page",
    "navigation",
    "navbar",
    "nav bar",
    "nav menu",
    "routing",
    "routes",
    "about page",
    "contact page",
    "dashboard page",
    "separate page",
    "another page",
    "second page",
    "menu link",
    "go to page",
    "sidebar link",
)


def _task_files(plan_data: dict) -> list[str]:
    files: list[str] = []
    for task in plan_data.get("tasks", []):
        files.extend(task.get("files", []))
    return files


def detect_uses_routing(
    user_content: str,
    plan_data: dict,
    *,
    architecture_file_structure: list[str] | None = None,
) -> bool:
    """Return True when the app should install react-router-dom."""
    lowered = user_content.lower()
    if any(keyword in lowered for keyword in ROUTING_KEYWORDS):
        return True
    if plan_data.get("uses_routing"):
        return True
    for path in _task_files(plan_data):
        if path.startswith("src/pages/"):
            return True
    if architecture_file_structure:
        for path in architecture_file_structure:
            if path.startswith("src/pages/"):
                return True
    return False
