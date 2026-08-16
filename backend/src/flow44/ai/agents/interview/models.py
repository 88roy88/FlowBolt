"""Pydantic models for InterviewAgent: clarifying questions and their answers."""

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

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
                logger.warning("[interview] Dropped malformed question: %s", item)
                continue
            kept.setdefault(question.id, question)
        return list(kept.values())[:MAX_QUESTIONS]
