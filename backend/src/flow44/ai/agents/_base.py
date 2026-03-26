from typing import Any

from langfuse.decorators import langfuse_context

from flow44.db.events import emit_event
from flow44.sandbox.main import PnpmSandbox


class BaseAgent:
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        if sandbox.project_id != project_id:
            raise ValueError(f"Sandbox project_id '{sandbox.project_id}' doesn't match agent project_id '{project_id}'")

        self.project_id = project_id
        self.sandbox = sandbox
        self.model = model
        self._trace_id = trace_id

    async def emit(self, event: dict[str, Any]) -> None:
        await emit_event(self.project_id, event)

    def _llm_metadata(self, generation_name: str) -> dict[str, Any]:
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        observation_id = langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }
