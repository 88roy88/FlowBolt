import asyncio
import json
import logging
from typing import Any

from langfuse.decorators import langfuse_context, observe

from flow44.ai.core.messages import Message
from flow44.ai.helpers import parse_json_response
from flow44.ai.prompts import (
    UX_DESIGN_PROMPT,
    render_architecture,
    render_data_source_analysis,
    render_user_plan,
)
from flow44.ai.provider import complete_chat
from flow44.ai.schemas import ArchitectureDesign, UserPlanOverview, UXDesign
from flow44.ai.state import BuildState
from flow44.db.pending_plan import save_pending_plan
from flow44.integrations.flapi_api import data_source_client
from flow44.sandbox.main import PnpmSandbox

from ._base import BaseAgent

logger = logging.getLogger(__name__)


class PlanAgent(BaseAgent):
    """Handles design and planning phases. Persists state to DB for ExecuteAgent."""

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        *,
        model: str | None = None,
        trace_id: str | None = None,
        data_source_authorization: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, model=model, trace_id=trace_id)
        self._state = BuildState(project_id=self.project_id, model=self.model)
        self._data_source_authorization = data_source_authorization

    @observe(name="plan-agent-run")  # type: ignore[untyped-decorator]
    async def run(self, content: str, data_source_ids: list[str] | None = None) -> None:
        self._state.user_content = content
        self._state.data_source_ids = data_source_ids or []
        self._trace_id = langfuse_context.get_current_trace_id()

        langfuse_context.update_current_trace(
            session_id=self.project_id,
            user_id=self.project_id,
            metadata={"model": self.model or "default"},
            tags=["plan-agent"],
        )

        # Fetch data source metadata
        if self._state.data_source_ids:
            await self.emit({"type": "phase", "phase": "fetching_data_sources"})
            try:
                results = await asyncio.gather(
                    *[self._fetch_and_analyze_data_source(sid) for sid in self._state.data_source_ids]
                )
            except Exception:
                await self.emit(
                    {"type": "error", "message": "Build aborted: failed to fetch required data source data."}
                )
                await self.emit({"type": "phase", "phase": "idle"})
                return
            self._state.data_source_contexts = [ctx for ctx in results if ctx is not None]

            if self._state.data_source_contexts:
                from flow44.db.project import update_project_data_sources  # noqa: PLC0415

                await update_project_data_sources(self.project_id, self._state.data_source_contexts)
                await self.emit(
                    {
                        "type": "data_sources_fetched",
                        "data_sources": [
                            {
                                "data_source_id": ctx["data_source_id"],
                                "data_source_name": ctx["data_source_name"],
                                "data_schema": ctx.get("data_schema", ""),
                                "relevant_fields": ctx.get("relevant_fields", ""),
                            }
                            for ctx in self._state.data_source_contexts
                        ],
                    }
                )

        # Design (parallel)
        await self.emit({"type": "phase", "phase": "designing"})
        self._state.architecture, self._state.ux_design = await asyncio.gather(
            self._design_architecture(),
            self._design_ux(),
        )

        # Build user overview
        await self.emit({"type": "phase", "phase": "planning"})
        self._state.user_overview = await self._build_user_overview()

        # Persist to DB and present for approval
        self._state.phase = "awaiting_approval"
        await save_pending_plan(self.project_id, self._state.model_dump_json())
        await self.emit({"type": "phase", "phase": "awaiting_approval"})
        await self.emit({"type": "plan_overview", "overview": self._state.user_overview.model_dump()})

    async def rebuild_with_feedback(self, state: BuildState, feedback: str) -> None:
        """Rebuild the user overview incorporating feedback, then persist."""
        self._state = state
        self._trace_id = langfuse_context.get_current_trace_id()

        await self.emit({"type": "phase", "phase": "planning"})

        plan_input = json.dumps(
            {
                "user_request": self._state.user_content,
                "architecture": self._state.architecture.model_dump(),
                "ux_design": self._state.ux_design.model_dump(),
                "previous_overview": self._state.user_overview.model_dump(),
                "user_feedback": feedback,
            },
            indent=2,
        )
        raw = await complete_chat(
            [Message.user(plan_input)],
            render_user_plan(has_feedback=True),
            model=self.model,
            metadata=self._llm_metadata("rebuild_user_plan"),
        )
        self._state.user_overview = UserPlanOverview.model_validate(parse_json_response(raw))

        self._state.phase = "awaiting_approval"
        await save_pending_plan(self.project_id, self._state.model_dump_json())
        await self.emit({"type": "phase", "phase": "awaiting_approval"})
        await self.emit({"type": "plan_overview", "overview": self._state.user_overview.model_dump()})

    # -- Design --

    async def _fetch_and_analyze_data_source(self, data_source_id: str) -> dict[str, Any]:
        ds_name, sample_data = await data_source_client.fetch_data_source(
            data_source_id,
            authorization=self._data_source_authorization,
        )
        analysis = await self._analyze_data_source(ds_name, sample_data)
        return {
            "data_source_id": data_source_id,
            "data_source_name": ds_name,
            "sample_data": sample_data,
            **analysis,
        }

    async def _analyze_data_source(self, ds_name: str, sample_data: Any) -> dict[str, Any]:
        prompt = render_data_source_analysis(
            user_content=self._state.user_content,
            data_source_name=ds_name,
            sample_data=sample_data,
        )
        try:
            raw = await complete_chat(
                [Message.user("Analyze this data source.")],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("data_source_analysis"),
            )
            return parse_json_response(raw)
        except Exception:
            logger.exception("[plan] Data source analysis failed, using degraded result")
            return {
                "data_schema": "Unable to analyze — see raw sample data",
                "relevant_fields": "See raw data",
                "data_characteristics": "Fetched from API",
                "integration_notes": f"Data preview: {json.dumps(sample_data, indent=2)[:500]}",
            }

    @observe(name="design-architecture")  # type: ignore[untyped-decorator]
    async def _design_architecture(self) -> ArchitectureDesign:
        prompt = render_architecture(data_source_contexts=self._state.data_source_contexts or None)
        try:
            raw = await complete_chat(
                [Message.user(self._state.user_content)],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("design_architecture"),
            )
            await self.emit({"type": "design_progress", "stream": "architecture", "content": "complete"})
            return ArchitectureDesign.model_validate(parse_json_response(raw))
        except Exception:
            logger.exception("[plan] Architecture design failed")
            await self.emit({"type": "design_progress", "stream": "architecture", "content": "failed"})
            return ArchitectureDesign()

    @observe(name="design-ux")  # type: ignore[untyped-decorator]
    async def _design_ux(self) -> UXDesign:
        try:
            raw = await complete_chat(
                [Message.user(self._state.user_content)],
                UX_DESIGN_PROMPT,
                model=self.model,
                metadata=self._llm_metadata("design_ux"),
            )
            await self.emit({"type": "design_progress", "stream": "ux", "content": "complete"})
            return UXDesign.model_validate(parse_json_response(raw))
        except Exception:
            logger.exception("[plan] UX design failed")
            await self.emit({"type": "design_progress", "stream": "ux", "content": "failed"})
            return UXDesign()

    @observe(name="build-user-overview")  # type: ignore[untyped-decorator]
    async def _build_user_overview(self) -> UserPlanOverview:
        plan_input = json.dumps(
            {
                "user_request": self._state.user_content,
                "architecture": self._state.architecture.model_dump(),
                "ux_design": self._state.ux_design.model_dump(),
            },
            indent=2,
        )
        raw = await complete_chat(
            [Message.user(plan_input)],
            render_user_plan(has_feedback=False),
            model=self.model,
            metadata=self._llm_metadata("build_user_plan"),
        )
        return UserPlanOverview.model_validate(parse_json_response(raw))
