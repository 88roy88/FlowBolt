import logging
import traceback as traceback_module
from typing import Any

from opik import get_global_client, opik_context
from opik.types import ErrorInfoDict

from flow44.db.events import emit_event
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)


class _NullSpan:
    """No-op stand-in for an Opik span, used when span creation itself fails (e.g. Opik
    unreachable) so the caller's actual work can still proceed uninterrupted."""

    id: str | None = None

    def end(self, **_kwargs: Any) -> None:
        pass


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
        trace_data = opik_context.get_current_trace_data()
        self._trace_id = trace_data.id if trace_data else None
        opik_context.update_current_trace(
            thread_id=self.project_id,
            metadata={"model": self.model or "default", "user_id": self._user_id},
            tags=[*tags, f"project:{self.project_id}"],
        )

    async def emit(self, event: dict[str, Any]) -> None:
        await emit_event(self.project_id, event)

    def _set_trace_output(self, output: dict[str, Any]) -> None:
        """Record a summary on the top-level trace so its outcome is visible without opening spans."""
        if opik_context.get_current_trace_data() is not None:
            opik_context.update_current_trace(output=output)

    @staticmethod
    def _safe_span(**kwargs: Any) -> Any:
        """Create a manual Opik span, tolerating failure in the creation call itself (e.g. Opik
        unreachable) — returns a no-op span instead of raising, so the actual agent work isn't
        aborted by an observability outage."""
        try:
            return get_global_client().span(**kwargs)
        except Exception:
            logger.exception("Failed to create Opik span %r", kwargs.get("name"))
            return _NullSpan()

    def _record_span_error(self, exc: Exception) -> None:
        """Mark the current @track-decorated span as failed, so a logged-and-swallowed
        exception still surfaces as an error in the Opik UI. No-op outside a tracked span
        (e.g. when a step is unit-tested directly, bypassing `run()`)."""
        if opik_context.get_current_span_data() is not None:
            opik_context.update_current_span(error_info=self._error_info(exc))

    @staticmethod
    def _error_info(exc: Exception) -> ErrorInfoDict:
        """Build Opik error info from a caught exception, so a logged-and-swallowed
        failure still surfaces as an error on the span in the Opik UI."""
        info: ErrorInfoDict = {
            "exception_type": type(exc).__name__,
            "traceback": "".join(traceback_module.format_exception(exc)),
        }
        message = str(exc)
        if message:
            info["message"] = message
        return info

    def _llm_metadata(
        self,
        generation_name: str,
        parent_span_id: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build Opik metadata for an LLM call.

        `parent_span_id` lets callers nest under a manually-created Opik span (e.g. a step
        span created via `Opik().span(...)`) — those aren't visible to `opik_context`, which
        only tracks spans created by the `@track` decorator.

        `extra_metadata` is merged into the span's top-level metadata (e.g. `available_tools`,
        `tool_calls`) — anything under `metadata["opik"]` besides `current_span_data` gets
        promoted straight into the span, same as `generation_name` already is.
        """
        span_data = opik_context.get_current_span_data()
        trace_id = self._trace_id or (span_data.trace_id if span_data else None)
        resolved_parent_span_id = parent_span_id or (span_data.id if span_data else None)
        opik_meta: dict[str, Any] = {
            "current_span_data": {"trace_id": trace_id, "id": resolved_parent_span_id},
            "generation_name": generation_name,
        }
        if extra_metadata:
            opik_meta.update(extra_metadata)
        return {"opik": opik_meta}
