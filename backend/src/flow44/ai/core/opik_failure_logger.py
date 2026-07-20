import logging
from datetime import datetime
from typing import Any

from litellm.integrations.opik.opik import OpikLogger
from litellm.integrations.opik.opik_payload_builder import extractors

logger = logging.getLogger(__name__)


class FailureAwareOpikLogger(OpikLogger):
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
        if self._opik_client is None:
            # No native Opik client available (e.g. `opik` package not installed) — the
            # batch-queue path this subclass would otherwise fall back to only knows how to
            # build success payloads, so there's nothing safe to do here.
            return  # type: ignore[unreachable]

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
