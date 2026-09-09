import logging
from collections.abc import Awaitable, Callable

from opik import track

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.interview.models import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewQuestionsPayload,
)
from flow44.ai.agents.interview.prompts import render_interview
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response
from flow44.ai.state import BuildState
from flow44.db.pending_plan import save_pending_plan

logger = logging.getLogger(__name__)

GatherContext = Callable[[str, list[str] | None], Awaitable[BuildState]]
ContinueWith = Callable[[BuildState], Awaitable[None]]


def _describe_values(question: InterviewQuestion, values: list[str]) -> str:
    described = {o.label: f"{o.label} ({o.description})" for o in question.options if o.description}
    return ", ".join(described.get(value, value) for value in values)


def _format_clarifications(questions: list[InterviewQuestion], answers: list[InterviewAnswer]) -> str:
    chosen = {a.question_id: a.values for a in answers if a.values}
    if not chosen:
        return ""
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
        continue_with: ContinueWith,
    ) -> None:
        self._setup_trace(["interview-agent"])

        state = await gather_context(content, data_source_ids)
        await self.emit({"type": "phase", "phase": "interviewing"})
        questions = await self._generate_questions(state)

        if not questions:
            await continue_with(state)
            return

        state.interview_questions = questions
        state.phase = "awaiting_interview"
        await save_pending_plan(self.project_id, state.model_dump_json())
        await self.emit({"type": "phase", "phase": "awaiting_interview"})
        await self.emit({"type": "interview_questions", "questions": [q.model_dump() for q in questions]})

    @track(name="interview-agent-resume", ignore_arguments=["state"])  # type: ignore[untyped-decorator]
    async def resume(
        self,
        state: BuildState,
        answers: list[InterviewAnswer],
        *,
        continue_with: ContinueWith,
    ) -> None:
        self._setup_trace(["interview-agent", "resume"])

        state.interview_answers = answers
        clarifications = _format_clarifications(state.interview_questions, answers)
        if clarifications:
            state.user_content = f"{state.user_content}\n\n{clarifications}"

        await self.emit(
            {
                "type": "interview_answered",
                "questions": [q.model_dump() for q in state.interview_questions],
                "answers": [a.model_dump() for a in answers],
            }
        )

        await continue_with(state)

    @track(name="generate-interview")  # type: ignore[untyped-decorator]
    async def _generate_questions(self, state: BuildState) -> list[InterviewQuestion]:
        try:
            raw = await complete_chat(
                [Message.user(state.user_content)],
                render_interview(data_source_contexts=state.data_source_contexts or None),
                model=self.model,
                metadata=self._llm_metadata("generate_interview"),
            )
            payload = InterviewQuestionsPayload.model_validate(parse_json_response(raw))
        except Exception:
            logger.exception("[interview] Question generation failed")
            return []
        return payload.questions
