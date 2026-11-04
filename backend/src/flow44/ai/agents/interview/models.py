from pydantic import BaseModel, Field

from flow44.db.project_data_source import DataSourceContext


class InterviewOption(BaseModel):
    label: str = Field(min_length=1)
    description: str = ""


class InterviewQuestion(BaseModel):
    id: str = Field(min_length=1)
    header: str = Field(min_length=1)
    question: str = Field(min_length=1)
    options: list[InterviewOption] = Field(min_length=2)
    multi_select: bool = False


class InterviewAnswer(BaseModel):
    question_id: str = Field(min_length=1)
    values: list[str] = Field(default_factory=list)


class InterviewSession(BaseModel):
    content: str
    data_source_ids: list[str] = Field(default_factory=list)
    data_source_contexts: list[DataSourceContext] = Field(default_factory=list)
    questions: list[InterviewQuestion] = Field(default_factory=list)
    model: str | None = None


class InterviewQuestionsPayload(BaseModel):
    questions: list[InterviewQuestion]
