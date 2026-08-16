import logging
import traceback as traceback_module
from datetime import datetime
from typing import Any

import litellm
import opik
from litellm.integrations.opik.opik import OpikLogger
from litellm.integrations.opik.opik_payload_builder import extractors
from opik import Span, get_global_client, opik_context
from opik.types import ErrorInfoDict

from flow44.config import settings

logger = logging.getLogger(__name__)


class FailureAwareOpikLogger(OpikLogger):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._opik_client = get_global_client()

    async def async_log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self._log_failure(kwargs, start_time, end_time)

    def log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self._log_failure(kwargs, start_time, end_time)

    def _log_failure(self, kwargs: dict[str, Any], start_time: datetime, end_time: datetime) -> None:
        try:
            exception = kwargs.get("exception")
            error_info = {
                "exception_type": type(exception).__name__ if exception else "Unknown",
                "traceback": str(kwargs.get("traceback_exception") or ""),
                "message": str(exception) if exception else "LLM call failed",
            }
            litellm_params = kwargs.get("litellm_params", {}) or {}
            litellm_metadata = litellm_params.get("metadata", {}) or {}
            standard_logging_object = kwargs.get("standard_logging_object", {}) or {}
            standard_logging_metadata = standard_logging_object.get("metadata", {}) or {}
            opik_metadata = extractors.extract_opik_metadata(litellm_metadata, standard_logging_metadata)
            current_span_data = opik_metadata.get("current_span_data")
            trace_id, parent_span_id = extractors.extract_span_identifiers(current_span_data)
            self._opik_client.span(
                trace_id=trace_id,
                parent_span_id=parent_span_id,
                name=f"{kwargs.get('model', 'unknown-model')}_failure",
                type="llm",
                model=kwargs.get("model"),
                start_time=start_time,
                end_time=end_time,
                input={"messages": kwargs.get("messages")},
                error_info=error_info,  # type: ignore[arg-type]
                project_name=self.opik_project_name,
            )
        except Exception:
            logger.exception("FailureAwareOpikLogger failed to log failure event")


def setup_trace(project_id: str, user_id: str, model: str | None, tags: list[str]) -> str | None:
    trace_data = opik_context.get_current_trace_data()
    opik_context.update_current_trace(
        thread_id=project_id,
        metadata={"model": model or "default", "user_id": user_id},
        tags=[*tags, f"project:{project_id}"],
    )
    return trace_data.id if trace_data else None


def set_trace_input(input_data: dict[str, Any]) -> None:
    if opik_context.get_current_trace_data() is not None:
        opik_context.update_current_trace(input=input_data)


def set_trace_output(output: dict[str, Any]) -> None:
    if opik_context.get_current_trace_data() is not None:
        opik_context.update_current_trace(output=output)


def create_span(**kwargs: Any) -> Span:
    return get_global_client().span(**kwargs)


def record_span_error(exc: Exception) -> None:
    if opik_context.get_current_span_data() is not None:
        opik_context.update_current_span(error_info=error_info(exc))


def error_info(exc: Exception) -> ErrorInfoDict:
    info: ErrorInfoDict = {
        "exception_type": type(exc).__name__,
        "traceback": "".join(traceback_module.format_exception(exc)),
    }
    message = str(exc)
    if message:
        info["message"] = message
    return info


def llm_metadata(
    trace_id: str | None,
    generation_name: str,
    parent_span_id: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    span_data = opik_context.get_current_span_data()
    resolved_trace_id = trace_id or (span_data.trace_id if span_data else None)
    resolved_parent_span_id = parent_span_id or (span_data.id if span_data else None)
    opik_meta: dict[str, Any] = {
        "current_span_data": {"trace_id": resolved_trace_id, "id": resolved_parent_span_id},
        "generation_name": generation_name,
    }
    if extra_metadata:
        opik_meta.update(extra_metadata)
    return {"opik": opik_meta}


def setup_opik_tracing() -> None:
    if not settings.OPIK_API_KEY:
        logger.info("Opik tracing not enabled (missing API key)")
        return
    litellm.callbacks = [FailureAwareOpikLogger()]
    logger.info("Opik tracing enabled")


def flush_opik_traces() -> None:
    if not settings.OPIK_API_KEY:
        return
    opik.flush_tracker()
    logger.info("Opik traces flushed.")
