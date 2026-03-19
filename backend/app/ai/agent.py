from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Awaitable

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

from app.ai.state import BuildState
from app.ai.core.messages import Message
from app.ai.helpers import encode_card, parse_json_response
from app.ai.provider import complete_chat
from app.ai.services.design import DesignService
from app.ai.services.planning import PlanningService
from app.ai.services.execution import ExecutionService
from app.ai.prompts import SUMMARY_PROMPT
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session, update_project_summary

logger = logging.getLogger(__name__)


class AgentOrchestrator:

    def __init__(
        self,
        session_id: str,
        project_id: str,
        ws_send: Callable[[dict], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.ws_send = ws_send

        self._state = BuildState(session_id=session_id, project_id=project_id)
        self._trace_id: str | None = None
        self._observation_id: str | None = None

        self._design = DesignService(ws_send=ws_send, llm_metadata=self._llm_metadata)
        self._planning = PlanningService(ws_send=ws_send, llm_metadata=self._llm_metadata)
        self._execution = ExecutionService(ws_send=ws_send, llm_metadata=self._llm_metadata)

    def _llm_metadata(self, generation_name: str) -> dict:
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        observation_id = self._observation_id or langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }

    # ------------------------------------------------------------------
    # Entry point: new user message
    # ------------------------------------------------------------------

    @observe(name="agent-handle-message")
    async def handle_message(
        self,
        content: str,
        model: str | None = None,
        case_ids: list[str] | None = None,
    ) -> None:
        self._state.model = model
        self._state.user_content = content
        self._state.case_ids = case_ids or []
        self._trace_id = langfuse_context.get_current_trace_id()
        self._execution._trace_id = self._trace_id

        langfuse_context.update_current_trace(
            session_id=self.session_id,
            user_id=self.project_id,
            metadata={"model": model or "default", "project_id": self.project_id},
            tags=["agent-flow", "new-message"],
        )

        # 1. Classify
        await self.ws_send({"type": "phase", "phase": "classifying"})
        is_new = await self._design.classify(self._state)

        if not is_new:
            from app.ai.followup_agent import FollowUpAgent

            agent = FollowUpAgent(
                session_id=self.session_id,
                project_id=self.project_id,
                ws_send=self.ws_send,
                model=model,
                trace_id=self._trace_id,
            )
            await agent.run(content)
            return

        # 2. Fetch case data
        if self._state.case_ids:
            await self.ws_send({"type": "phase", "phase": "fetching_cases"})
            results = await asyncio.gather(
                *[self._design.fetch_and_analyze_case(self._state, cid) for cid in self._state.case_ids]
            )
            self._state.case_contexts = [ctx for ctx in results if ctx is not None]

            if self._state.case_contexts:
                from app.models.project import update_project_cases
                await update_project_cases(self.project_id, self._state.case_contexts)

                await self.ws_send({
                    "type": "cases_fetched",
                    "cases": [
                        {
                            "package_id": ctx["package_id"],
                            "package_name": ctx["package_name"],
                            "data_schema": ctx.get("data_schema", ""),
                            "relevant_fields": ctx.get("relevant_fields", ""),
                        }
                        for ctx in self._state.case_contexts
                    ],
                })
                await save_message(self.project_id, "assistant", encode_card({
                    "type": "cases_fetched",
                    "cases": [
                        {
                            "packageId": ctx["package_id"],
                            "packageName": ctx["package_name"],
                            "dataSchema": ctx.get("data_schema", ""),
                            "relevantFields": ctx.get("relevant_fields", ""),
                        }
                        for ctx in self._state.case_contexts
                    ],
                }))

        # 3. Design (parallel)
        await self.ws_send({"type": "phase", "phase": "designing"})
        self._state.architecture, self._state.ux_design = await asyncio.gather(
            self._design.design_architecture(self._state),
            self._design.design_ux(self._state),
        )

        await save_message(self.project_id, "assistant", encode_card({
            "type": "design_complete",
            "architecture": bool(self._state.architecture),
            "ux": bool(self._state.ux_design),
        }))

        # 4. Build user overview
        await self.ws_send({"type": "phase", "phase": "planning"})
        self._state.user_overview = await self._design.build_user_overview(self._state)

        # 5. Present for approval
        self._state.phase = "awaiting_approval"
        await self.ws_send({"type": "phase", "phase": "awaiting_approval"})
        await self.ws_send({"type": "plan_overview", "overview": self._state.user_overview})

    # ------------------------------------------------------------------
    # Plan response (accept / modify / reject)
    # ------------------------------------------------------------------

    async def handle_plan_response(self, action: str, feedback: str | None = None) -> None:
        if action == "accept":
            await save_message(self.project_id, "assistant", encode_card({
                "type": "plan_overview",
                "overview": self._state.user_overview,
                "accepted": True,
            }))

            langfuse_client = Langfuse()

            # Build technical plan
            await self.ws_send({"type": "phase", "phase": "planning"})
            span_plan = langfuse_client.span(trace_id=self._trace_id, name="build-technical-plan")
            self._observation_id = span_plan.id
            self._state.work_plan = await self._planning.build_technical_plan(self._state)
            span_plan.end()

            await self.ws_send({
                "type": "task_list",
                "tasks": [
                    {"id": t.id, "title": t.title, "status": t.status}
                    for t in self._state.work_plan.tasks
                ],
            })

            # Execute
            span_exec = langfuse_client.span(
                trace_id=self._trace_id, name="execute-plan",
                metadata={
                    "total_tasks": len(self._state.work_plan.tasks),
                    "execution_layers": len(self._state.work_plan.execution_layers()),
                },
            )
            self._observation_id = span_exec.id
            self._execution._observation_id = span_exec.id
            await self.ws_send({"type": "phase", "phase": "executing"})
            self._state = await self._execution.execute(self._state)
            span_exec.end()

            # Save task progress
            await save_message(self.project_id, "assistant", encode_card({
                "type": "task_progress",
                "tasks": [
                    {"id": t.id, "title": t.title, "status": t.status}
                    for t in self._state.work_plan.tasks
                ],
            }))

            # Summary
            span_summary = langfuse_client.span(trace_id=self._trace_id, name="generate-summary")
            self._observation_id = span_summary.id
            await self._generate_summary()
            span_summary.end()
            self._observation_id = None

            self._state.phase = "idle"
            self._state.work_plan = None
            await self.ws_send({"type": "phase", "phase": "complete"})
            await self.ws_send({"type": "action_complete"})

        elif action == "modify":
            if feedback:
                await self.ws_send({"type": "phase", "phase": "planning"})
                self._state.user_overview = await self._design.rebuild_overview_with_feedback(
                    self._state, feedback,
                )
                self._state.phase = "awaiting_approval"
                await self.ws_send({"type": "phase", "phase": "awaiting_approval"})
                await self.ws_send({"type": "plan_overview", "overview": self._state.user_overview})

        elif action == "reject":
            self._state = BuildState(session_id=self.session_id, project_id=self.project_id)
            await self.ws_send({"type": "phase", "phase": "idle"})

    # ------------------------------------------------------------------
    # Fix error (user-triggered "Fix with AI" button)
    # ------------------------------------------------------------------

    @observe(name="fix-error-direct")
    async def handle_fix_error(
        self,
        error_message: str,
        error_file: str | None = None,
        error_line: int | None = None,
        error_stack: str | None = None,
        model: str | None = None,
    ) -> None:
        self._state.model = model
        self._trace_id = langfuse_context.get_current_trace_id()

        from app.ai.fix_error_agent import FixErrorAgent

        agent = FixErrorAgent(
            session_id=self.session_id,
            project_id=self.project_id,
            ws_send=self.ws_send,
            model=model,
            trace_id=self._trace_id,
            llm_metadata=self._llm_metadata,
        )
        await agent.run(
            error_message=error_message,
            error_file=error_file,
            error_line=error_line,
            error_stack=error_stack,
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def _generate_summary(self) -> None:
        try:
            summary_input = json.dumps({
                "user_request": self._state.user_content,
                "architecture": self._state.architecture,
                "files_created": list(self._state.completed_files.keys()),
            }, indent=2)

            messages = [Message.user(summary_input)]
            raw = await complete_chat(
                messages, SUMMARY_PROMPT, model=self._state.model,
                metadata=self._llm_metadata("generate_summary"),
            )
            summary_data = parse_json_response(raw)

            if summary_data:
                summary_json = json.dumps(summary_data, ensure_ascii=False)
                await update_project_summary(self.project_id, summary_json)
                await self.ws_send({"type": "project_summary", "summary": summary_data})
        except Exception:
            logger.exception("[agent] Summary generation failed")


# Backward-compatible exports
CARD_PREFIX = "<!--agent-card:"
CARD_SUFFIX = "-->"
