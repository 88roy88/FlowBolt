from __future__ import annotations

from langfuse.decorators import langfuse_context

from app.models.events import emit_event


class BaseAgent:

    def __init__(
        self,
        session_id: str,
        project_id: str,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.model = model
        self._trace_id = trace_id

    async def emit(self, event: dict) -> None:
        await emit_event(self.session_id, event)

    def _llm_metadata(self, generation_name: str) -> dict:
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        observation_id = langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }
