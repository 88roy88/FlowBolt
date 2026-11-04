import asyncio
import functools
import logging
import time
import traceback as traceback_module
from collections.abc import Callable
from datetime import datetime
from typing import Any

import litellm
import opik
from litellm.integrations.opik.opik import OpikLogger
from litellm.integrations.opik.opik_payload_builder import extractors
from opik import Span, get_global_client, opik_context
from opik.rest_api.errors import NotFoundError
from opik.types import ErrorInfoDict

from flow44.config import settings
from flow44.services.logging import _project_name as _log_project_name

logger = logging.getLogger(__name__)

_MAX_TAG_LENGTH = 100
_THREAD_WAIT_ATTEMPTS = 15
_THREAD_WAIT_SECONDS = 2.0


class RunCancelled(Exception):
    pass


def track(**options: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """opik.track for coroutines that also closes the span when the task is cancelled.

    opik.track only handles Exception, so a CancelledError would leave the span and trace open.
    The exception swap stays inside the decorator, so callers still see a real CancelledError
    and their `except Exception` recovery paths can't swallow the cancellation.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def cancellable(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError as exc:
                raise RunCancelled("Cancelled") from exc

        tracked = opik.track(**options)(cancellable)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await tracked(*args, **kwargs)
            except RunCancelled as exc:
                raise asyncio.CancelledError from exc

        return wrapper

    return decorator


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


def _project_name_tags() -> list[str]:
    project_name = _log_project_name.get()
    return [f"project_name:{project_name}"[:_MAX_TAG_LENGTH]] if project_name else []


def setup_trace(project_id: str, user_id: str, model: str | None, tags: list[str]) -> str | None:
    trace_data = opik_context.get_current_trace_data()
    opik_context.update_current_trace(
        thread_id=project_id,
        metadata={"model": model or "default", "user_id": user_id, "project_name": _log_project_name.get()},
        tags=[*tags, f"project:{project_id}", *_project_name_tags()],
    )
    return trace_data.id if trace_data else None


def _tag_thread(thread_id: str, tags: list[str]) -> None:
    client = get_global_client().rest_client.traces
    for _ in range(_THREAD_WAIT_ATTEMPTS):
        try:
            thread = client.get_trace_thread(
                thread_id=thread_id, project_name=settings.OPIK_PROJECT_NAME, truncate=True
            )
            if thread.thread_model_id:
                client.update_thread(thread.thread_model_id, tags=tags)
            return
        except NotFoundError:
            # A new thread only exists once Opik has stored its first finished trace.
            time.sleep(_THREAD_WAIT_SECONDS)
        except Exception:
            logger.exception("Failed to tag Opik thread %s", thread_id)
            return
    logger.warning("Opik thread %s never appeared, leaving it untagged", thread_id)


def tag_thread(thread_id: str) -> None:
    """Trace tags don't reach the thread, which has its own tags. Call this once a run has finished."""
    tags = _project_name_tags()
    if tags and settings.OPIK_API_KEY:
        asyncio.get_running_loop().run_in_executor(None, _tag_thread, thread_id, tags)


def set_trace_input(input_data: dict[str, Any]) -> None:
    if opik_context.get_current_trace_data() is not None:
        opik_context.update_current_trace(input=input_data)


def set_trace_output(output: dict[str, Any]) -> None:
    if opik_context.get_current_trace_data() is not None:
        opik_context.update_current_trace(output=output)


def add_trace_tags(tags: list[str]) -> None:
    if opik_context.get_current_trace_data() is not None:
        opik_context.update_current_trace(tags=tags)


def create_span(**kwargs: Any) -> Span:
    return get_global_client().span(**kwargs)


def update_span(**fields: Any) -> None:
    if opik_context.get_current_span_data() is not None:
        opik_context.update_current_span(**fields)


def record_span_error(exc: Exception) -> None:
    if opik_context.get_current_span_data() is not None:
        opik_context.update_current_span(error_info=error_info(exc))


def error_info(exc: BaseException) -> ErrorInfoDict:
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
