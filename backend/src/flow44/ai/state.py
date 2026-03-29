from typing import Any

from pydantic import BaseModel, Field

from flow44.ai.schemas import ArchitectureDesign, UserPlanOverview, UXDesign
from flow44.ai.task_tree import WorkPlan


class BuildState(BaseModel):
    project_id: str
    model: str | None = None
    user_content: str = ""
    data_source_ids: list[str] = Field(default_factory=list)
    data_source_contexts: list[dict[str, Any]] = Field(
        default_factory=list
    )  # TODO: type with DataSourceAnalysis + raw data
    architecture: ArchitectureDesign = Field(default_factory=ArchitectureDesign)
    ux_design: UXDesign = Field(default_factory=UXDesign)
    user_overview: UserPlanOverview = Field(default_factory=UserPlanOverview)
    work_plan: WorkPlan | None = None
    completed_files: dict[str, str] = Field(default_factory=dict)
    task_files: dict[str, list[str]] = Field(default_factory=dict)

    # Flow control
    phase: str = "idle"

    model_config = {"arbitrary_types_allowed": True}
