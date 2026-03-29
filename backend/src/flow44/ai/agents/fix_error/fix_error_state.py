"""Fix error state for Flow orchestration in FixErrorAgent."""
from typing import Any

from pydantic import BaseModel, Field


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
    full_response: str = ""
    validation_errors: str = ""
    retry_count: int = 0

    class Config:
        arbitrary_types_allowed = True
