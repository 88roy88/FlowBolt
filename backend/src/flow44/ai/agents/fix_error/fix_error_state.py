"""Fix error state for Flow orchestration in FixErrorAgent."""

from typing import Any

from pydantic import BaseModel, Field

from flow44.ai.agents.file_diffs import DiffTracker
from flow44.ai.file_safety import FileSafetyError


class FixErrorState(BaseModel):
    """State that flows through FixErrorAgent's Flow steps."""

    # Input
    project_id: str
    sandbox_ref: Any = None
    emit_fn: Any = None
    model: str | None = None
    llm_metadata_fn: Any = None

    # Error details
    error_message: str
    error_file: str | None = None
    error_line: int | None = None
    error_stack: str | None = None

    # Working state
    discovered_files: dict[str, str] = Field(default_factory=dict)
    generated_files: list[tuple[str, str]] = Field(default_factory=list)
    diffs: DiffTracker = Field(default_factory=DiffTracker)
    full_response: str = ""
    explanation: str = ""
    validation_errors: str = ""
    retry_count: int = 0
    rejected_files: list[FileSafetyError] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
