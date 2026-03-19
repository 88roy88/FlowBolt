from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Awaitable, Callable

from langfuse.decorators import observe, langfuse_context

from app.ai.core.messages import Message
from app.ai.provider import complete_chat
from app.ai.prompts import render_merge
from app.ai.state import BuildState
from app.ai.task_tree import Task, WorkPlan
from app.ai.helpers import parse_json_response

logger = logging.getLogger(__name__)


class PlanningService:
    def __init__(
        self,
        ws_send: Callable[[dict], Awaitable[None]],
        llm_metadata: Callable[[str], dict],
    ) -> None:
        self.ws_send = ws_send
        self._llm_metadata = llm_metadata

    @observe(name="build-technical-plan")
    async def build_technical_plan(self, state: BuildState) -> WorkPlan:
        merge_data: dict = {
            "user_request": state.user_content,
            "architecture": state.architecture,
            "ux_design": state.ux_design,
            "user_preferences": state.user_overview.get("decisions", []),
        }

        if state.case_contexts:
            merge_data["case_integrations"] = [
                {
                    "package_id": ctx["package_id"],
                    "package_name": ctx["package_name"],
                    "data_schema": ctx["data_schema"],
                    "relevant_fields": ctx["relevant_fields"],
                    "data_characteristics": ctx["data_characteristics"],
                    "integration_notes": ctx["integration_notes"],
                }
                for ctx in state.case_contexts
            ]

        system_prompt = render_merge(has_cases=bool(state.case_contexts))
        messages = [Message.user(json.dumps(merge_data, indent=2))]

        raw = await complete_chat(
            messages, system_prompt, model=state.model,
            metadata=self._llm_metadata("build_technical_plan"),
        )
        plan_data = parse_json_response(raw)

        tasks = []
        for t in plan_data.get("tasks", []):
            tasks.append(Task(
                id=t.get("id", f"task-{uuid.uuid4().hex[:6]}"),
                title=t.get("title", "Untitled task"),
                description=t.get("description", ""),
                files=t.get("files", []),
                depends_on=t.get("depends_on", []),
            ))

        work_plan = WorkPlan(
            id=f"plan-{uuid.uuid4().hex[:8]}",
            summary=plan_data.get("summary", ""),
            architecture=state.architecture,
            ux_design=state.ux_design,
            tasks=tasks,
        )

        langfuse_context.update_current_observation(
            metadata={"tasks_count": len(tasks)}
        )
        return work_plan
