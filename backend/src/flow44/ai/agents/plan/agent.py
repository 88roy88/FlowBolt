import asyncio
import json
import logging
from typing import Any

from langfuse.decorators import langfuse_context, observe

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.plan.models import ArchitectureDesign, UserPlanOverview, UXDesign
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.agents.plan.prompts import (
    UX_DESIGN_PROMPT,
    render_architecture,
    render_data_source_analysis,
    render_user_plan,
)
from flow44.ai.codegen.data_source_module import generate_data_source_module
from flow44.ai.codegen.ts_types import sanitize_to_pascal_case
from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response
from flow44.ai.state import BuildState
from flow44.db.pending_plan import save_pending_plan
from flow44.logic import data_source as ds_logic
from flow44.logic.models import DataSourceParamsInfo, DataSourceQuerySchema
from flow44.sandbox.main import PnpmSandbox

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
        self._flow = self._build_flow()

    def _build_flow(self) -> Flow[PlanState]:
        """Build the planning flow with explicit steps."""
        flow = Flow[PlanState]("plan")

        flow.add_step("fetch_data_sources", self._step_fetch_data_sources, next_step="design")
        flow.add_step("design", self._step_design, next_step="build_overview")
        flow.add_step("build_overview", self._step_build_overview, next_step="persist")
        flow.add_step("persist", self._step_persist, next_step=None)

        return flow

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

        # Initialize plan state for Flow
        plan_state = PlanState(
            build_state=self._state,
            project_id=self.project_id,
            sandbox_ref=self.sandbox,
            emit_fn=self.emit,
            model=self.model,
            trace_id=self._trace_id,
            llm_metadata_fn=self._llm_metadata,
            data_source_authorization=self._data_source_authorization,
        )

        # Run the flow
        start_step = "fetch_data_sources" if self._state.data_source_ids else "design"
        await self._flow.run(plan_state, start=start_step)

    # -- Flow Steps --

    async def _step_fetch_data_sources(self, state: PlanState) -> PlanState:
        """Step: Fetch and analyze data sources."""
        await state.emit_fn({"type": "phase", "phase": "fetching_data_sources"})

        try:
            results = await asyncio.gather(
                *[self._fetch_and_analyze_data_source(sid) for sid in state.build_state.data_source_ids]
            )
        except Exception:
            await state.emit_fn(
                {"type": "error", "message": "Build aborted: failed to fetch required data source data."}
            )
            await state.emit_fn({"type": "phase", "phase": "idle"})
            raise

        state.build_state.data_source_contexts = [ctx for ctx in results if ctx is not None]

        # Generate deterministic hook + type files and write to sandbox
        for ctx in state.build_state.data_source_contexts:
            generated = self._generate_data_source_files(ctx)
            ctx["generated_files"] = generated
            for path, content in generated.items():
                await state.sandbox_ref.write_file(path, content)
            state.build_state.generated_data_source_files.update(generated)

        if state.build_state.data_source_contexts:
            from flow44.db.project import update_project_data_sources  # noqa: PLC0415

            await update_project_data_sources(state.project_id, state.build_state.data_source_contexts)
            await state.emit_fn(
                {
                    "type": "data_sources_fetched",
                    "data_sources": [
                        {
                            "data_source_id": ctx["data_source_id"],
                            "data_source_name": ctx["data_source_name"],
                            "data_schema": ctx.get("data_schema", ""),
                            "relevant_fields": ctx.get("relevant_fields", ""),
                            "requires_input": not ctx.get("can_run_without_input", True),
                            "params": [
                                {
                                    "name": p["name"],
                                    "display_name": p["display_name"],
                                    "type": p["type"],
                                    "is_required": p["is_required"],
                                    "is_single_value": p["is_single_value"],
                                }
                                for p in ctx.get("params_info", {}).get("parameters", [])
                            ],
                        }
                        for ctx in state.build_state.data_source_contexts
                    ],
                }
            )

        return state

    async def _step_design(self, state: PlanState) -> PlanState:
        """Step: Design architecture and UX in parallel."""
        await state.emit_fn({"type": "phase", "phase": "designing"})

        state.build_state.architecture, state.build_state.ux_design = await asyncio.gather(
            self._design_architecture(),
            self._design_ux(),
        )

        return state

    async def _step_build_overview(self, state: PlanState) -> PlanState:
        """Step: Build user overview from designs."""
        await state.emit_fn({"type": "phase", "phase": "planning"})

        state.build_state.user_overview = await self._build_user_overview()

        return state

    async def _step_persist(self, state: PlanState) -> PlanState:
        """Step: Persist to DB and emit plan for approval."""
        state.build_state.phase = "awaiting_approval"
        await save_pending_plan(state.project_id, state.build_state.model_dump_json())
        await state.emit_fn({"type": "phase", "phase": "awaiting_approval"})
        await state.emit_fn({"type": "plan_overview", "overview": state.build_state.user_overview.model_dump()})

        return state

    # -- Rebuild --

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
        ds_name, usage = await asyncio.gather(
            ds_logic.get_display_name(data_source_id, authorization=self._data_source_authorization),
            ds_logic.get_usage(data_source_id, authorization=self._data_source_authorization),
        )
        sanitized = sanitize_to_pascal_case(ds_name) or f"DataSource{data_source_id}"
        analysis = await self._analyze_data_source(ds_name, usage.sample, usage.queries, usage.params)
        return {
            "data_source_id": data_source_id,
            "data_source_name": ds_name,
            "sanitized_name": sanitized,
            "queries": [q.model_dump() for q in usage.queries],
            "params_info": usage.params.model_dump(),
            "sample_data": usage.sample,
            "can_run_without_input": usage.can_run,
            **analysis,
        }

    @staticmethod
    def _generate_data_source_files(ctx: dict[str, Any]) -> dict[str, str]:
        """Generate a single TypeScript module per data source."""
        sanitized = ctx["sanitized_name"]
        module_path = f"src/dataSources/{sanitized}.ts"
        params_info = DataSourceParamsInfo.model_validate(ctx["params_info"])
        queries = [DataSourceQuerySchema.model_validate(q) for q in ctx.get("queries", [])]
        content = generate_data_source_module(
            data_source_id=ctx["data_source_id"],
            sanitized_name=sanitized,
            params_info=params_info,
            sample_data=ctx.get("sample_data"),
            queries=queries,
        )
        return {module_path: content}

    async def _analyze_data_source(
        self,
        ds_name: str,
        sample_data: Any,
        queries: list[Any],
        params_info: Any,
    ) -> dict[str, Any]:
        prompt = render_data_source_analysis(
            user_content=self._state.user_content,
            data_source_name=ds_name,
            sample_data=sample_data,
            queries=[q.model_dump() for q in queries],
            params_info=params_info.model_dump(),
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
                "data_schema": "Unknown — analysis failed",
                "relevant_fields": "See raw data",
                "data_characteristics": (
                    "Requires user input" if sample_data is None else "Fetched from API"
                ),
                "integration_notes": (
                    f"Data preview: {json.dumps(sample_data, indent=2)[:500]}"
                    if sample_data is not None
                    else "No sample available — data source requires parameters."
                ),
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
