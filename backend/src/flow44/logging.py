import logging
import logging.handlers

from pythonjsonlogger.json import JsonFormatter


def setup_logging(log_file_path: str | None = None) -> None:
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    handlers: list[logging.Handler] = [console]

    if log_file_path:
        file = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=1024 * 1024, backupCount=5)
        file.setFormatter(
            JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                rename_fields={"asctime": "@timestamp", "levelname": "level"},
                json_ensure_ascii=False,
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        handlers.append(file)

    logging.basicConfig(level=logging.INFO, handlers=handlers)
