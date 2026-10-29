from collections.abc import Awaitable, Callable
from typing import Protocol

from opik import track

from flow44.ai.agents._base import BaseAgent
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

Continue = Callable[[str, str], Awaitable[None]]


class PausedState(Protocol):
    data_source_contexts: list[DataSourceContext]

    def model_dump_json(self) -> str: ...


GatherContext = Callable[[str, list[str] | None], Awaitable[PausedState]]


def _describe_values(question: InterviewQuestion, values: list[str]) -> str:
    described = {o.label: f"{o.label} ({o.description})" for o in question.options if o.description}
    return ", ".join(described.get(value, value) for value in values)


def _format_clarifications(questions: list[InterviewQuestion], answers: list[InterviewAnswer]) -> str:
    if not answers:
        return ""
    chosen = {a.question_id: a.values for a in answers if a.values}
    lines = [
        f"- {q.question}: {_describe_values(q, chosen[q.id])}"
        if q.id in chosen
        else f"- {q.question}: no preference given — pick a sensible default"
        for q in questions
    ]
    return "Clarifications from the user:\n" + "\n".join(lines)


class InterviewAgent(BaseAgent):
    @track(name="interview-agent-run")  # type: ignore[untyped-decorator]
    async def run(
        self,
        content: str,
        data_source_ids: list[str] | None = None,
        *,
        gather_context: GatherContext,
        paused_agent: str,
        continue_with: Continue,
    ) -> None:
        self._setup_trace(["interview-agent"])

        state = await gather_context(content, data_source_ids)
        await self.emit({"type": "phase", "phase": "interviewing"})
        questions = await self._generate_questions(content, state.data_source_contexts)

        if not questions:
            await continue_with(content, state.model_dump_json())
            return

        session = InterviewSession(
            content=content,
            questions=questions,
            paused_agent=paused_agent,
            paused_state=state.model_dump_json(),
            model=self.model,
        )
        await pause_turn(self.project_id, "awaiting_interview", session.model_dump_json())
        await self.emit({"type": "phase", "phase": "awaiting_interview"})
        await self.emit({"type": "interview_questions", "questions": [q.model_dump() for q in questions]})

    @track(name="interview-agent-resume", ignore_arguments=["session"])  # type: ignore[untyped-decorator]
    async def resume(
        self,
        session: InterviewSession,
        answers: list[InterviewAnswer],
        *,
        continue_with: Continue,
    ) -> None:
        self._setup_trace(["interview-agent", "resume"])

        await self.emit(
            {
                "type": "interview_answered",
                "questions": [q.model_dump() for q in session.questions],
                "answers": [a.model_dump() for a in answers],
            }
        )

        clarifications = _format_clarifications(session.questions, answers)
        content = f"{session.content}\n\n{clarifications}" if clarifications else session.content
        await continue_with(content, session.paused_state)

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
