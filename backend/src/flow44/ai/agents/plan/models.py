"""Pydantic models for PlanAgent: architecture, UX, and user plan overview."""

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
