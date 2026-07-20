from typing import Any

from flow44.ai.core.opik_failure_logger import llm_metadata, set_trace_output, setup_trace
from flow44.db.events import emit_event
from flow44.sandbox.main import PnpmSandbox


class BaseAgent:
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        user_id: str,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        if sandbox.project_id != project_id:
            raise ValueError(f"Sandbox project_id '{sandbox.project_id}' doesn't match agent project_id '{project_id}'")

        self.project_id = project_id
        self.sandbox = sandbox
        self._user_id = user_id
        self.model = model
        self._trace_id = trace_id

    def _setup_trace(self, tags: list[str]) -> None:
        self._trace_id = setup_trace(self.project_id, self._user_id, self.model, tags)

    async def emit(self, event: dict[str, Any]) -> None:
        await emit_event(self.project_id, event)

    def _set_trace_output(self, output: dict[str, Any]) -> None:
        set_trace_output(output)

    def _llm_metadata(
        self,
        generation_name: str,
        parent_span_id: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return llm_metadata(self._trace_id, generation_name, parent_span_id, extra_metadata)
