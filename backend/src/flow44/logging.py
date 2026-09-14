import logging
import logging.handlers
import socket
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pythonjsonlogger.json import JsonFormatter

if TYPE_CHECKING:
    from flow44.ai.agents.file_diffs import FileDiff
    from flow44.db.project_data_source import DataSourceContext

__all__ = [
    "_client_app_version",
    "_project_id",
    "_project_name",
    "_source",
    "_user_id",
    "log_bi_event",
    "log_data_sources_added",
    "log_file_diffs",
    "setup_logging",
]

_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_project_id: ContextVar[str | None] = ContextVar("project_id", default=None)
_project_name: ContextVar[str | None] = ContextVar("project_name", default=None)
_source: ContextVar[str] = ContextVar("source", default="server")
_client_app_version: ContextVar[str | None] = ContextVar("client_app_version", default=None)


class RequestContextFilter(logging.Filter):
    _hostname = socket.gethostname()

    def filter(self, record: logging.LogRecord) -> bool:
        record.hostname = self._hostname
        if user_id := _user_id.get():
            record.user_id = user_id
        if project_id := _project_id.get():
            record.project_id = project_id
        if project_name := _project_name.get():
            record.project_name = project_name
        record.source = _source.get()
        if client_app_version := _client_app_version.get():
            record.client_app_version = client_app_version
        return True


def setup_logging(log_file_path: str | None = None) -> None:
    context_filter = RequestContextFilter()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    console.addFilter(context_filter)

    handlers: list[logging.Handler] = [console]

    if log_file_path:
        file = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=5)
        format_str = (
            "%(asctime)s %(hostname)s %(name)s %(levelname)s %(user_id)s "
            "%(project_id)s %(project_name)s %(source)s %(client_app_version)s %(message)s"
        )
        file.setFormatter(
            JsonFormatter(
                format_str,
                rename_fields={"asctime": "@timestamp", "levelname": "level"},
                json_ensure_ascii=False,
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        file.addFilter(context_filter)
        handlers.append(file)

    logging.basicConfig(level=logging.INFO, handlers=handlers)


def log_bi_event(
    event: str,
    properties: dict[str, Any] | None = None,
    *,
    event_version: int = 1,
    level: str = "info",
) -> None:
    logger = logging.getLogger("bi_events")

    payload = {
        "event": event,
        "event_version": event_version,
        "timestamp": datetime.now(UTC).isoformat(),
        **(properties or {}),
    }

    logger.log(getattr(logging, level.upper(), logging.INFO), payload)


def log_data_sources_added(contexts: list["DataSourceContext"]) -> None:
    for ctx in contexts:
        log_bi_event(
            "data_source_added",
            {
                "data_source_type": ctx.type,
                "data_source_id": ctx.data_source_id,
            },
        )


def log_file_diffs(diffs: list["FileDiff"]) -> None:
    if not diffs:
        return

    line_count_added = 0
    line_count_removed = 0

    for diff in diffs:
        for line in diff.diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                line_count_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                line_count_removed += 1

    log_bi_event(
        "code_generated",
        {
            "response_id": str(uuid.uuid4()),
            "file_count": len(diffs),
            "line_count_added": line_count_added,
            "line_count_removed": line_count_removed,
        },
    )

    for diff in diffs:
        if diff.is_new:
            file_type = diff.path.split(".")[-1] if "." in diff.path else ""
            log_bi_event(
                "file_created",
                {
                    "file_path": diff.path,
                    "file_type": file_type,
                    "created_by": "model",
                },
            )
