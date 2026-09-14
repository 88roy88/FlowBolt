from typing import Any

from fastapi import APIRouter, Header

from flow44.api.deps import UserDep
from flow44.logging import (
    _client_app_version,
    _project_name as _log_project_name,
    _source,
    emit_bi_event,
)

router = APIRouter(prefix="/api/bi", tags=["bi_events"])


@router.post("/events")
async def log_event(
    events: list[dict[str, Any]],
    user_id: UserDep,
    x_client_version: str | None = Header(None),
) -> dict[str, str]:
    _source.set("web_client")
    if x_client_version:
        _client_app_version.set(x_client_version)

    for event_data in events:
        event_name = event_data.get("event", "unknown")
        event_version = event_data.get("event_version", 1)
        level = event_data.get("level", "info")
        properties = event_data.get("properties", {})
        if project_name := event_data.get("project_name"):
            _log_project_name.set(project_name)
        emit_bi_event(event_name, properties, event_version=event_version, level=level)

    return {"status": "ok"}
