import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header

from flow44.api.deps import UserDep
from flow44.services.logging import (
    _client_app_version,
    _source,
    log_bi_event,
)
from flow44.services.logging import _project_id as _log_project_id
from flow44.services.logging import _project_name as _log_project_name

router = APIRouter(prefix="/api/bi", tags=["bi_events"])

_RESERVED_PROPERTIES = ("event_version", "level", "timestamp")


def _parse_timestamp(value: Any) -> datetime | None:
    """Parse the client's ISO 8601 timestamp; None (server time) if missing or invalid."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


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
        level = logging.getLevelNamesMapping().get(str(event_data.get("level", "info")).upper(), logging.INFO)
        timestamp = _parse_timestamp(event_data.get("timestamp"))
        properties = {k: v for k, v in event_data.get("properties", {}).items() if k not in _RESERVED_PROPERTIES}
        _log_project_id.set(event_data.get("project_id"))
        _log_project_name.set(event_data.get("project_name"))
        log_bi_event(event_name, event_version=event_version, level=level, timestamp=timestamp, **properties)

    return {"status": "ok"}
