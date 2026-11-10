from __future__ import annotations

import json
import logging
from typing import Any, cast

from flow44.ai.file_safety import FileSafetyError

logger = logging.getLogger(__name__)


def format_summary(raw: str) -> str:
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        return "(no project summary available)"
    return (
        f"{data.get('summary', '')}\n"
        f"Tech stack: {', '.join(data.get('tech_stack', []))}\n"
        f"Features: {', '.join(data.get('features', []))}\n"
    )


def format_agent_feedback(build_errors: str, rejected_files: list[FileSafetyError]) -> str:
    sections: list[str] = []
    if build_errors:
        sections.append(f"## Build errors\n{build_errors}")
    if rejected_files:
        rejected = "\n".join(f"- {rejection}" for rejection in rejected_files)
        sections.append(
            "## Changes that could not be applied\n"
            f"{rejected}\n"
            "Re-emit their logic in the same flowArtifact format using an allowed path."
        )
    return "\n\n".join(sections)


# TODO: get rid of this when moving to structured output
def parse_json_response(raw: str | None) -> dict[str, Any]:
    if raw is None:
        logger.error("[helpers] Received None response from LLM")
        return {}

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines[1:] if line.strip() != "```"]
        text = "\n".join(lines)
    try:
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return cast(dict[str, Any], json.loads(text[start:end]))
            except json.JSONDecodeError:
                pass
        logger.error("[helpers] Failed to parse JSON from: %s", text[:200])
        return {}
