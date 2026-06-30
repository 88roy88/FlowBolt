"""Build state that flows between PlanAgent and ExecuteAgent."""

from pydantic import BaseModel, Field

from flow44.ai.agents.execute.models import WorkPlan
from flow44.ai.agents.optional_packages import OptionalPackageDecision
from flow44.ai.agents.plan.models import ArchitectureDesign, UserPlanOverview, UXDesign
from flow44.db.project_data_source import DataSourceContext

__all__ = ["BuildState"]


class BuildState(BaseModel):
    """State that persists across plan and execute phases."""

    project_id: str
    model: str | None = None
    user_content: str = ""
    data_source_ids: list[str] = Field(default_factory=list)
    data_source_contexts: list[DataSourceContext] = Field(default_factory=list)
    generated_data_source_files: dict[str, str] = Field(default_factory=dict)
    architecture: ArchitectureDesign = Field(default_factory=ArchitectureDesign)
    ux_design: UXDesign = Field(default_factory=UXDesign)
    optional_package_decision: OptionalPackageDecision | None = None
    user_overview: UserPlanOverview = Field(default_factory=UserPlanOverview)
    work_plan: WorkPlan | None = None
    completed_files: dict[str, str] = Field(default_factory=dict)
    task_files: dict[str, list[str]] = Field(default_factory=dict)

    # Flow control
    phase: str = "idle"
