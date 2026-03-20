"""Agent prompt modules."""

from app.ai.prompts.classify import CLASSIFY_PROMPT
from app.ai.prompts.architecture import ARCHITECTURE_PROMPT
from app.ai.prompts.ux_design import UX_DESIGN_PROMPT
from app.ai.prompts.merge import MERGE_PROMPT
from app.ai.prompts.user_plan import USER_PLAN_PROMPT
from app.ai.prompts.codegen import get_codegen_prompt
from app.ai.prompts.summary import SUMMARY_PROMPT
from app.ai.prompts.followup import FOLLOWUP_SYSTEM_PROMPT, FOLLOWUP_TOOLS

__all__ = [
    "CLASSIFY_PROMPT",
    "ARCHITECTURE_PROMPT",
    "UX_DESIGN_PROMPT",
    "MERGE_PROMPT",
    "USER_PLAN_PROMPT",
    "get_codegen_prompt",
    "SUMMARY_PROMPT",
    "FOLLOWUP_SYSTEM_PROMPT",
    "FOLLOWUP_TOOLS",
]
