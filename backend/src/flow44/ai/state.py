from __future__ import annotations

from pydantic import BaseModel, Field

from flow44.ai.task_tree import WorkPlan


# TODO: what is this?
class BuildState(BaseModel):
    session_id: str
    project_id: str
    model: str | None = None
    user_content: str = ""
    case_ids: list[str] = Field(default_factory=list)
    case_contexts: list[dict] = Field(default_factory=list)
    architecture: dict = Field(default_factory=dict)
    ux_design: dict = Field(default_factory=dict)
    user_overview: dict = Field(default_factory=dict)
    work_plan: WorkPlan | None = None
    completed_files: dict[str, str] = Field(default_factory=dict)
    task_files: dict[str, list[str]] = Field(default_factory=dict)

    # Flow control
    phase: str = "idle"

    model_config = {"arbitrary_types_allowed": True}
