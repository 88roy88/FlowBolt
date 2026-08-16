from __future__ import annotations

from flow44.ai.agents.enhance.prompts import render_enhance
from flow44.ai.core.messages import Message
from flow44.ai.core.opik_failure_logger import llm_metadata
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import format_summary


async def enhance_prompt(
    content: str,
    *,
    is_new: bool,
    summary: str,
    model: str | None,
    data_source_names: list[str],
) -> str:
    system_prompt = render_enhance(
        is_new_project=is_new,
        project_summary=format_summary(summary),
        data_source_names=data_source_names,
    )
    enhanced = await complete_chat(
        [Message.user(content)],
        system_prompt,
        model=model,
        metadata=llm_metadata(None, "enhance_prompt"),
    )
    return enhanced.strip()
