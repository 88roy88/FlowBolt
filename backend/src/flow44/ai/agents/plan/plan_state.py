"""Plan state for Flow orchestration in PlanAgent."""
from typing import Any

from pydantic import BaseModel

from flow44.ai.state import BuildState


class PlanState(BaseModel):
    """State that flows through PlanAgent's Flow steps."""

    # Input
    build_state: BuildState
    project_id: str
    sandbox_ref: Any = None
    emit_fn: Any = None
    model: str | None = None
    trace_id: str | None = None
    llm_metadata_fn: Any = None
    data_source_authorization: str | None = None

    # For rebuild_with_feedback
    feedback: str | None = None

    class Config:
        arbitrary_types_allowed = True
