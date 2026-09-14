import uuid
from typing import TYPE_CHECKING

from flow44.services.logging import log_bi_event

if TYPE_CHECKING:
    from flow44.ai.agents.file_diffs import FileDiff
    from flow44.db.project_data_source import DataSourceContext

__all__ = [
    "log_data_sources_added",
    "log_file_diffs",
]


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
