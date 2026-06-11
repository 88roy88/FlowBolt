"""Build state that flows between PlanAgent and ExecuteAgent."""

from typing import Any, NotRequired, TypedDict

from pydantic import BaseModel, Field

from flow44.ai.agents.execute.models import WorkPlan
from flow44.ai.agents.plan.models import ArchitectureDesign, UserPlanOverview, UXDesign


class DataSourceContext(TypedDict):
    """Data source metadata and generated analysis"""

    data_source_id: str
    data_source_name: str
    sanitized_name: str
    queries: list[dict[str, Any]]  # DataSourceQuerySchema dumps
    params_info: dict[str, Any]  # DataSourceParamsInfo dump
    can_run_without_input: bool

    # LLM analysis (see plan/templates/data_source_analysis.jinja2)
    data_schema: str
    relevant_fields: str
    data_characteristics: str
    integration_notes: str
    param_ux_hints: str

    # Optional (held in memory during the plan, but not persisted to the DB)
    sample_data: NotRequired[dict[str, Any] | None]
    module_path: NotRequired[str]
    generated_files: NotRequired[dict[str, str]]


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
    user_overview: UserPlanOverview = Field(default_factory=UserPlanOverview)
    work_plan: WorkPlan | None = None
    completed_files: dict[str, str] = Field(default_factory=dict)
    task_files: dict[str, list[str]] = Field(default_factory=dict)

    # Flow control
    phase: str = "idle"
