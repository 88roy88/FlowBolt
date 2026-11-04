from flow44.ai.agents.followup.agent import FollowUpAgent
from flow44.ai.agents.interview.agent import InterviewAgent
from flow44.ai.agents.interview.models import InterviewAnswer, InterviewSession
from flow44.ai.agents.plan.agent import PlanAgent
from flow44.db.events import get_latest_event
from flow44.sandbox.main import PnpmSandbox


async def is_new_project(project_id: str) -> bool:
    return await get_latest_event(project_id, "action_complete") is None


class AgentRouter:
    def __init__(
        self, project_id: str, sandbox: PnpmSandbox, *, user_id: str, data_source_authorization: str | None
    ) -> None:
        self._project_id = project_id
        self._sandbox = sandbox
        self._user_id = user_id
        self._data_source_authorization = data_source_authorization

    async def handle_message(
        self, content: str, data_source_ids: list[str] | None, *, model: str | None, interview: bool
    ) -> None:
        new_project = await is_new_project(self._project_id)
        if interview and new_project:
            session = await self._interviewer(model).ask(content, data_source_ids)
            if not session.questions:
                await self._continue(self._agent(model, new_project), content, session)
            return
        await self._agent(model, new_project).run(content, data_source_ids)

    async def resume_interview(
        self, session: InterviewSession, answers: list[InterviewAnswer], *, model: str | None
    ) -> None:
        content = await self._interviewer(model).apply_answers(session, answers)
        await self._continue(self._agent(model, await is_new_project(self._project_id)), content, session)

    def _agent(self, model: str | None, new_project: bool) -> PlanAgent | FollowUpAgent:
        agent_cls = PlanAgent if new_project else FollowUpAgent
        return agent_cls(
            self._project_id,
            self._sandbox,
            user_id=self._user_id,
            model=model,
            data_source_authorization=self._data_source_authorization,
        )

    def _interviewer(self, model: str | None) -> InterviewAgent:
        return InterviewAgent(
            self._project_id,
            self._sandbox,
            user_id=self._user_id,
            model=model,
            data_source_authorization=self._data_source_authorization,
        )

    async def _continue(self, agent: PlanAgent | FollowUpAgent, content: str, session: InterviewSession) -> None:
        if isinstance(agent, PlanAgent):
            await agent.run(content, session.data_source_ids, data_source_contexts=session.data_source_contexts)
            return
        await agent.run(content, session.data_source_ids)
