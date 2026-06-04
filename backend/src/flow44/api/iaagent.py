from __future__ import annotations

from fastapi import APIRouter

from flow44.ai.agent_runtime import is_agent_active
from flow44.api.deps import ProjectDep
from flow44.db.events import get_events

router = APIRouter(prefix="/api/iaagent", tags=["iaagent"])


async def _latest_phase(project_id: str) -> str | None:
    events = await get_events(project_id)
    for evt in reversed(events):
        if evt.payload.get("type") == "phase":
            phase = evt.payload.get("phase")
            if isinstance(phase, str):
                return phase
    return None


@router.get("/{project_id}/alive")
async def iaagent_alive(project: ProjectDep) -> dict[str, bool | str]:
    """Report whether a background agent task is running for this project."""
    alive = is_agent_active(project.id)
    phase = await _latest_phase(project.id) if alive else "idle"
    return {"alive": alive, "phase": phase or "idle"}
