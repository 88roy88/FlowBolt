"""Agent prompt modules."""

from app.ai.prompts.classify import CLASSIFY_PROMPT
from app.ai.prompts.architecture import ARCHITECTURE_PROMPT
from app.ai.prompts.ux_design import UX_DESIGN_PROMPT
from app.ai.prompts.merge import MERGE_PROMPT
from app.ai.prompts.codegen import get_codegen_prompt

__all__ = [
    "CLASSIFY_PROMPT",
    "ARCHITECTURE_PROMPT",
    "UX_DESIGN_PROMPT",
    "MERGE_PROMPT",
    "get_codegen_prompt",
]
