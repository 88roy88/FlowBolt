from opik import track

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.analyze_data_source import fetch_data_sources
from flow44.ai.agents.interview.models import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewQuestionsPayload,
    InterviewSession,
)
from flow44.ai.agents.interview.prompts import render_interview
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response
from flow44.db.paused_turn import pause_turn
from flow44.db.project_data_source import DataSourceContext
from flow44.sandbox.main import PnpmSandbox


def _describe_values(question: InterviewQuestion, values: list[str]) -> str:
    described = {o.label: f"{o.label} ({o.description})" for o in question.options if o.description}
    return ", ".join(described.get(value, value) for value in values)


def _format_clarifications(questions: list[InterviewQuestion], answers: list[InterviewAnswer]) -> str:
    chosen = {a.question_id: a.values for a in answers if a.values}
    lines = [
        f"- {q.question}: {_describe_values(q, chosen[q.id])}"
        if q.id in chosen
        else f"- {q.question}: no preference given — pick a sensible default"
        for q in questions
    ]
    return "Clarifications from the user:\n" + "\n".join(lines)


class InterviewAgent(BaseAgent):
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        *,
        user_id: str,
        model: str | None = None,
        trace_id: str | None = None,
        data_source_authorization: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, user_id, model=model, trace_id=trace_id)
        self._data_source_authorization = data_source_authorization

    @track(name="interview-agent-run")  # type: ignore[untyped-decorator]
    async def ask(self, content: str, data_source_ids: list[str] | None = None) -> InterviewSession:
        self._setup_trace(["interview-agent"])

        ids = data_source_ids or []
        contexts: list[DataSourceContext] = []
        if ids:
            contexts = await fetch_data_sources(
                ids, content, self._data_source_authorization, self.model, self._llm_metadata, self.emit
            )
        await self.emit({"type": "phase", "phase": "interviewing"})
        questions = await self._generate_questions(content, contexts)

        session = InterviewSession(
            content=content,
            data_source_ids=ids,
            data_source_contexts=contexts,
            questions=questions,
            model=self.model,
        )
        if not questions:
            return session

        await pause_turn(self.project_id, "awaiting_interview", session.model_dump_json())
        await self.emit({"type": "phase", "phase": "awaiting_interview"})
        await self.emit({"type": "interview_questions", "questions": [q.model_dump() for q in questions]})
        return session

    @track(name="interview-agent-answers", ignore_arguments=["session"])  # type: ignore[untyped-decorator]
    async def apply_answers(self, session: InterviewSession, answers: list[InterviewAnswer]) -> str:
        self._setup_trace(["interview-agent", "answers"])

        await self.emit(
            {
                "type": "interview_answered",
                "questions": [q.model_dump() for q in session.questions],
                "answers": [a.model_dump() for a in answers],
            }
        )

        if not answers:
            return session.content
        return f"{session.content}\n\n{_format_clarifications(session.questions, answers)}"

    @track(name="generate-interview")  # type: ignore[untyped-decorator]
    async def _generate_questions(
        self, content: str, data_source_contexts: list[DataSourceContext]
    ) -> list[InterviewQuestion]:
        raw = await complete_chat(
            [Message.user(content)],
            render_interview(data_source_contexts=data_source_contexts or None),
            model=self.model,
            metadata=self._llm_metadata("generate_interview"),
        )
        return InterviewQuestionsPayload.model_validate(parse_json_response(raw)).questions
