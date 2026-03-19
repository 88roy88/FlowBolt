from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from langfuse.decorators import observe, langfuse_context

from app.ai.core.messages import Message
from app.ai.provider import complete_chat
from app.ai.prompts import (
    ARCHITECTURE_PROMPT,
    UX_DESIGN_PROMPT,
    USER_PLAN_PROMPT,
    render_user_plan,
)
from app.ai.state import BuildState
from app.ai.helpers import parse_json_response
from app.integrations.package_api import PackageApiClient, PackageApiUpstreamError
from app.config import settings

logger = logging.getLogger(__name__)


class DesignService:
    def __init__(
        self,
        ws_send: Callable[[dict], Awaitable[None]],
        llm_metadata: Callable[[str], dict],
    ) -> None:
        self.ws_send = ws_send
        self._llm_metadata = llm_metadata

    @observe(name="classify-request")
    async def classify(self, state: BuildState) -> bool:
        from app.models.chat import get_messages

        history = await get_messages(state.project_id)
        assistant_msgs = [m for m in history if m.role == "assistant"]
        is_new = len(assistant_msgs) == 0
        langfuse_context.update_current_observation(
            metadata={"classification": "new_project" if is_new else "follow_up"}
        )
        return is_new

    async def fetch_and_analyze_case(self, state: BuildState, package_id: str) -> dict | None:
        try:
            package_api = PackageApiClient(base_url=settings.PACKAGE_API_BASE_URL)
            search_results = await package_api.search(package_id)
            if not search_results:
                await self.ws_send({"type": "case_error", "message": f"Package {package_id} not found"})
                return None

            package_metadata = search_results[0] if isinstance(search_results, list) else search_results
            package_name = package_metadata.get("Name", f"Package {package_id}")
            sample_data = await package_api.run_package(package_id, all_queries=True, body=None)

            analysis_prompt = f"""Analyze this API package data in the context of the user's request.

User wants to build: {state.user_content}

Package: {package_name}
Sample API Response:
```json
{json.dumps(sample_data, indent=2)[:2000]}
```

Respond with ONLY a JSON object:
{{
  "data_schema": "Brief description of the data structure",
  "relevant_fields": "Which fields are most important for the user's request",
  "data_characteristics": "Key properties: volume, data type, update frequency, etc.",
  "integration_notes": "Technical details: endpoint usage, parameters, response format"
}}"""

            messages = [Message.user(analysis_prompt)]
            try:
                raw = await complete_chat(
                    messages,
                    "You are a software architect analyzing API data for integration.",
                    model=state.model,
                    metadata=self._llm_metadata("package_analysis"),
                )
                analysis = parse_json_response(raw)
            except Exception:
                logger.exception("[design] Package analysis failed")
                data_preview = json.dumps(sample_data, indent=2)[:500]
                analysis = {
                    "data_schema": f"Package data with {len(sample_data) if isinstance(sample_data, list) else 'structured'} records",
                    "relevant_fields": "See raw data",
                    "data_characteristics": "Fetched from API",
                    "integration_notes": f"Data preview: {data_preview}",
                }

            return {
                "package_id": package_id,
                "package_name": package_name,
                "sample_data": sample_data,
                **analysis,
            }

        except PackageApiUpstreamError as e:
            await self.ws_send({"type": "case_error", "message": f"Failed to fetch package data: {e}"})
            return None
        except Exception:
            logger.exception("[design] Unexpected error fetching package")
            await self.ws_send({"type": "case_error", "message": "Unexpected error fetching package data"})
            return None

    @observe(name="design-architecture")
    async def design_architecture(self, state: BuildState) -> dict:
        user_message = state.user_content
        if state.case_contexts:
            case_sections = []
            for ctx in state.case_contexts:
                case_sections.append(
                    f"### Case: {ctx['package_name']} (ID: {ctx['package_id']})\n"
                    f"Data Schema: {ctx['data_schema']}\n"
                    f"Relevant Fields: {ctx['relevant_fields']}\n"
                    f"Data Characteristics: {ctx['data_characteristics']}\n"
                    f"Sample data:\n```json\n{json.dumps(ctx['sample_data'], indent=2)[:1000]}\n```\n"
                    f"Integration Notes: {ctx['integration_notes']}\n"
                    f"Endpoint: /api/package/{ctx['package_id']}/run"
                )
            user_message += (
                "\n\n## Case Data Integration\n\n"
                + "\n\n".join(case_sections)
                + "\n\nYour architecture MUST include components that fetch, display, and interact with this case data."
            )

        messages = [Message.user(user_message)]
        try:
            raw = await complete_chat(
                messages, ARCHITECTURE_PROMPT, model=state.model,
                metadata=self._llm_metadata("design_architecture"),
            )
            await self.ws_send({"type": "design_progress", "stream": "architecture", "content": "complete"})
            return parse_json_response(raw)
        except Exception:
            logger.exception("[design] Architecture design failed")
            await self.ws_send({"type": "design_progress", "stream": "architecture", "content": "failed"})
            return {}

    @observe(name="design-ux")
    async def design_ux(self, state: BuildState) -> dict:
        messages = [Message.user(state.user_content)]
        try:
            raw = await complete_chat(
                messages, UX_DESIGN_PROMPT, model=state.model,
                metadata=self._llm_metadata("design_ux"),
            )
            await self.ws_send({"type": "design_progress", "stream": "ux", "content": "complete"})
            return parse_json_response(raw)
        except Exception:
            logger.exception("[design] UX design failed")
            await self.ws_send({"type": "design_progress", "stream": "ux", "content": "failed"})
            return {}

    @observe(name="build-user-overview")
    async def build_user_overview(self, state: BuildState) -> dict:
        plan_input = json.dumps({
            "user_request": state.user_content,
            "architecture": state.architecture,
            "ux_design": state.ux_design,
        }, indent=2)
        messages = [Message.user(plan_input)]
        raw = await complete_chat(
            messages, USER_PLAN_PROMPT, model=state.model,
            metadata=self._llm_metadata("build_user_overview"),
        )
        return parse_json_response(raw)

    async def rebuild_overview_with_feedback(self, state: BuildState, feedback: str) -> dict:
        plan_input = json.dumps({
            "user_request": state.user_content,
            "architecture": state.architecture,
            "ux_design": state.ux_design,
            "previous_overview": state.user_overview,
            "user_feedback": feedback,
        }, indent=2)
        messages = [Message.user(plan_input)]
        raw = await complete_chat(
            messages,
            render_user_plan(has_feedback=True),
            model=state.model,
            metadata=self._llm_metadata("rebuild_overview_with_feedback"),
        )
        return parse_json_response(raw)
