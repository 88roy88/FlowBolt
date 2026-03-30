"""Execution state for Flow orchestration in ExecuteAgent."""

from typing import Any

from pydantic import BaseModel

from flow44.ai.state import BuildState


class ExecutionState(BaseModel):
    """State that flows through ExecuteAgent's Flow steps."""

    # Input
    build_state: BuildState
    project_id: str
    sandbox_ref: Any = None  # Can't serialize sandbox, just hold reference
    emit_fn: Any = None  # Can't serialize function
    model: str | None = None
    trace_id: str | None = None
    observation_id: str | None = None
    langfuse_client: Any = None  # Hold reference
    llm_metadata_fn: Any = None  # Function to generate metadata

    # Validation results
    typecheck_errors: str = ""
    build_errors: str = ""
    all_errors: str = ""
    fix_attempts: int = 0

    class Config:
        arbitrary_types_allowed = True
