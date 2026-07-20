"""Execution state for Flow orchestration in ExecuteAgent."""

from typing import Any

from pydantic import BaseModel, Field

from flow44.ai.file_safety import FileSafetyError
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
    root_span_id: str | None = None  # The `run()` @track span — parent for top-level step spans
    observation_id: str | None = None
    opik_client: Any = None  # Hold reference
    llm_metadata_fn: Any = None  # Function to generate metadata

    # Validation results
    typecheck_errors: str = ""
    build_errors: str = ""
    all_errors: str = ""
    fix_attempts: int = 0
    rejected_files: list[FileSafetyError] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
