from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

CARD_PREFIX = "<!--agent-card:"
CARD_SUFFIX = "-->"


def encode_card(card_data: dict) -> str:
    return f"{CARD_PREFIX}{json.dumps(card_data, separators=(',', ':'))}{CARD_SUFFIX}"


def parse_json_response(raw: str | None) -> dict:
    if raw is None:
        logger.error("[helpers] Received None response from LLM")
        return {}

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines[1:] if line.strip() != "```"]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        logger.error("[helpers] Failed to parse JSON from: %s", text[:200])
        return {}
