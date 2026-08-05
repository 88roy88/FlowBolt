"""Pydantic models for PlanAgent: architecture, UX, and user plan overview."""

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

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
    key_dependencies: str | list[str] = ""
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


# --- Interview (clarifying questions before planning) ---

MAX_QUESTIONS = 4
MAX_OPTIONS = 4
MAX_ANSWER_VALUES = 10
MAX_ANSWER_LENGTH = 200


class InterviewOption(BaseModel):
    label: str = Field(min_length=1)
    description: str = ""


class InterviewQuestion(BaseModel):
    id: str = Field(min_length=1)
    header: str = Field(min_length=1)
    question: str = Field(min_length=1)
    options: list[InterviewOption] = Field(min_length=2)
    multi_select: bool = False

    @field_validator("options", mode="before")
    @classmethod
    def _cap_options(cls, options: Any) -> Any:
        return options[:MAX_OPTIONS] if isinstance(options, list) else options

    @field_validator("options")
    @classmethod
    def _validate_unique_option_labels(cls, options: list[InterviewOption]) -> list[InterviewOption]:
        labels = [option.label.strip() for option in options]
        if len(labels) != len(set(labels)):
            msg = "Interview options must have unique labels"
            raise ValueError(msg)
        return options


class InterviewAnswer(BaseModel):
    question_id: str = Field(min_length=1)
    values: list[str] = Field(default_factory=list)

    @field_validator("values")
    @classmethod
    def _clean(cls, values: list[str]) -> list[str]:
        return [value.strip()[:MAX_ANSWER_LENGTH] for value in values if value.strip()][:MAX_ANSWER_VALUES]


class InterviewQuestionsPayload(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)

    @field_validator("questions", mode="before")
    @classmethod
    def _keep_valid(cls, items: Any) -> list[InterviewQuestion]:
        if not isinstance(items, list):
            return []
        kept: dict[str, InterviewQuestion] = {}
        for item in items:
            try:
                question = InterviewQuestion.model_validate(item)
            except ValidationError:
                logger.warning("[plan] Dropped malformed interview question: %s", item)
                continue
            kept.setdefault(question.id, question)
        return list(kept.values())[:MAX_QUESTIONS]


# --- Data source analysis ---


class DataSourceAnalysis(BaseModel):
    data_schema: str = ""
    relevant_fields: str = ""
    data_characteristics: str = ""
    integration_notes: str = ""
    param_ux_hints: str = ""
