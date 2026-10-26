from __future__ import annotations

from fastapi import APIRouter

from flow44.api.deps import ProjectDep
from flow44.db.events import get_latest_event
from flow44.db.heartbeat import is_run_active

router = APIRouter(prefix="/api/iaagent", tags=["iaagent"])


async def _latest_phase(project_id: str) -> str | None:
    event = await get_latest_event(project_id, "phase")
    phase = event.payload.get("phase") if event else None
    return phase if isinstance(phase, str) else None


@router.get("/{project_id}/alive")
async def iaagent_alive(project: ProjectDep) -> dict[str, bool | str]:
    """Report whether a background agent task is running for this project."""
    alive = await is_run_active(project.id)
    phase = await _latest_phase(project.id) if alive else "idle"
    return {"alive": alive, "phase": phase or "idle"}
