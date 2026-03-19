from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from langfuse.decorators import langfuse_context


class BaseAgent(ABC):

    def __init__(
        self,
        session_id: str,
        project_id: str,
        ws_send: Callable[[dict], Awaitable[None]],
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.ws_send = ws_send
        self.model = model
        self._trace_id = trace_id

    def _llm_metadata(self, generation_name: str) -> dict:
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        observation_id = langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }
