"""AI-assisted optional package selection shared by agents."""

from __future__ import annotations

import json
import logging
from typing import Any

from jinja2 import Environment, FileSystemLoader
from pydantic import ValidationError

from flow44.ai.agents.optional_packages import (
    OptionalPackageDecision,
    high_confidence_optional_package_decision,
    merge_optional_package_decisions,
    optional_packages_prompt_context,
    validate_optional_package_decision,
)
from flow44.ai.agents.template_paths import TEMPLATE_PROMPTS_PATH
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response

logger = logging.getLogger(__name__)

_env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML; autoescape would break them
    loader=FileSystemLoader(str(TEMPLATE_PROMPTS_PATH)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_package_decision() -> str:
    return _env.get_template("package_decision.jinja2").render(optional_packages=optional_packages_prompt_context())


async def decide_optional_packages(
    *,
    user_request: str,
    context: dict[str, Any],
    model: str | None,
    metadata: dict[str, Any] | None,
    ai_enabled: bool,
    log_label: str,
) -> OptionalPackageDecision:
    """Select optional packages using AI when enabled, plus deterministic high-confidence signals."""
    high_confidence_decision = high_confidence_optional_package_decision(user_request)
    if not ai_enabled:
        return high_confidence_decision

    decision_input = json.dumps(
        {
            "user_request": user_request,
            **context,
        },
        indent=2,
        ensure_ascii=False,
    )
    raw = await complete_chat(
        [Message.user(decision_input)],
        render_package_decision(),
        model=model,
        metadata=metadata,
    )
    try:
        decision = OptionalPackageDecision.model_validate(parse_json_response(raw))
        return merge_optional_package_decisions(
            validate_optional_package_decision(decision),
            high_confidence_decision,
        )
    except ValidationError:
        logger.warning("[%s] Invalid optional package decision; using high-confidence package signals", log_label)
        return high_confidence_decision
