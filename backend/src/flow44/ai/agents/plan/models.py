"""Pydantic models for the plan agent: design schemas, build state."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Architecture design ---


class ArchitectureComponent(BaseModel):
    name: str
    file: str
    purpose: str


class ArchitectureDesign(BaseModel):
    components: list[ArchitectureComponent] = Field(default_factory=list)
    data_flow: str = ""
    file_structure: list[str] = Field(default_factory=list)
    state_management: str = ""
    key_dependencies: str = ""
    notes: str = ""


# --- UX design ---


class UXComponent(BaseModel):
    name: str
    layout: str
    interactions: str


class UXDesign(BaseModel):
    layout: str = ""
    color_scheme: str = ""
    components_ui: list[UXComponent] = Field(default_factory=list)
    animations: str = ""
    accessibility: str = ""
    notes: str = ""


# --- User plan overview ---


class PlanFeature(BaseModel):
    title: str
    description: str


class PlanDecision(BaseModel):
    id: str
    title: str
    chosen: str
    alternatives: list[str] = Field(default_factory=list)


class UserPlanOverview(BaseModel):
    summary: str = ""
    features: list[PlanFeature] = Field(default_factory=list)
    decisions: list[PlanDecision] = Field(default_factory=list)


# --- Data source analysis ---


class DataSourceAnalysis(BaseModel):
    data_schema: str = ""
    relevant_fields: str = ""
    data_characteristics: str = ""
    integration_notes: str = ""


# --- Build state (handoff from PlanAgent → ExecuteAgent) ---


class BuildState(BaseModel):
    project_id: str
    model: str | None = None
    user_content: str = ""
    data_source_ids: list[str] = Field(default_factory=list)
    data_source_contexts: list[dict[str, Any]] = Field(default_factory=list)
    architecture: ArchitectureDesign = Field(default_factory=ArchitectureDesign)
    ux_design: UXDesign = Field(default_factory=UXDesign)
    user_overview: UserPlanOverview = Field(default_factory=UserPlanOverview)
    work_plan: Any = None  # WorkPlan (from execute/models) — typed as Any to avoid circular import
    completed_files: dict[str, str] = Field(default_factory=dict)
    task_files: dict[str, list[str]] = Field(default_factory=dict)
    phase: Literal["idle", "designing", "planning", "awaiting_approval", "executing", "fixing", "complete"] = "idle"
