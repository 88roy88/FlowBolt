import logging
import logging.handlers
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_project_id: ContextVar[str | None] = ContextVar("project_id", default=None)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = _user_id.get()  # type: ignore[attr-defined]
        record.project_id = _project_id.get()  # type: ignore[attr-defined]
        return True


def setup_logging(log_file_path: str | None = None) -> None:
    context_filter = RequestContextFilter()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    console.addFilter(context_filter)

    handlers: list[logging.Handler] = [console]

    if log_file_path:
        file = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=5)
        file.setFormatter(
            JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(user_id)s %(project_id)s %(message)s",
                rename_fields={"asctime": "@timestamp", "levelname": "level"},
                json_ensure_ascii=False,
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        file.addFilter(context_filter)
        handlers.append(file)

    logging.basicConfig(level=logging.INFO, handlers=handlers)
