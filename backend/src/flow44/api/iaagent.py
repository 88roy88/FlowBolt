from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from flow44.ai.agent_runtime import is_agent_active
from flow44.db.events import get_events
from flow44.db.project import get_project

router = APIRouter(prefix="/api/iaagent", tags=["iaagent"])

_ACTIVE_PHASES = frozenset(
    {
        "fetching_data_sources",
        "designing",
        "planning",
        "executing",
        "fixing",
        "exploring",
    }
)


async def _latest_phase(project_id: str) -> str | None:
    events = await get_events(project_id)
    for evt in reversed(events):
        if evt.payload.get("type") == "phase":
            phase = evt.payload.get("phase")
            if isinstance(phase, str):
                return phase
    return None


@router.get("/{project_id}/alive")
async def iaagent_alive(project_id: str) -> dict[str, Any]:
    """Report whether a background agent task is running for this project."""
    project = await get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown project")

    alive = is_agent_active(project_id)
    phase = await _latest_phase(project_id)

    if not alive:
        if phase is None or phase in _ACTIVE_PHASES:
            phase = "idle"
    elif phase is None:
        phase = "idle"

    return {"alive": alive, "phase": phase}
