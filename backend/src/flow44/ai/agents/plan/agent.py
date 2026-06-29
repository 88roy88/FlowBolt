import asyncio
import json
import logging

from langfuse.decorators import observe

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.analyze_data_source import fetch_and_analyze_data_source, generate_data_source_files
from flow44.ai.agents.plan.models import ArchitectureDesign, UserPlanOverview, UXDesign
from flow44.ai.agents.plan.plan_state import PlanState
from flow44.ai.agents.plan.prompts import (
    UX_DESIGN_PROMPT,
    render_architecture,
    render_user_plan,
)
from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat
from flow44.ai.helpers import parse_json_response
from flow44.ai.state import BuildState
from flow44.db.pending_plan import save_pending_plan
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)


class PlanAgent(BaseAgent):
    """Handles design and planning phases. Persists state to DB for ExecuteAgent."""

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        *,
        user_id: str,
        model: str | None = None,
        trace_id: str | None = None,
        data_source_authorization: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, user_id, model=model, trace_id=trace_id)
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
        self._setup_trace(["plan-agent"])

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
                *[
                    fetch_and_analyze_data_source(
                        sid,
                        self._state.user_content,
                        self._data_source_authorization,
                        self.model,
                        self._llm_metadata,
                    )
                    for sid in state.build_state.data_source_ids
                ]
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
            generated = generate_data_source_files(ctx)
            ctx.module_path = next(iter(generated))
            ctx.generated_files = generated
            for path, content in generated.items():
                await state.sandbox_ref.write_file(path, content)
            state.build_state.generated_data_source_files.update(generated)

        if state.build_state.data_source_contexts:
            from flow44.db.project_data_source import update_project_data_sources  # noqa: PLC0415

            await update_project_data_sources(state.project_id, state.build_state.data_source_contexts)
            await state.emit_fn(
                {
                    "type": "data_sources_fetched",
                    "data_sources": [
                        {
                            "data_source_id": ctx.data_source_id,
                            "data_source_name": ctx.data_source_name,
                            "data_schema": ctx.data_schema,
                            "relevant_fields": ctx.relevant_fields,
                            "requires_input": not ctx.can_run_without_input,
                            "params": [
                                {
                                    "name": p["name"],
                                    "display_name": p["display_name"],
                                    "type": p["type"],
                                    "is_required": p["is_required"],
                                    "is_single_value": p["is_single_value"],
                                }
                                for p in ctx.params_info.get("parameters", [])
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

    @observe(name="plan-agent-rebuild")  # type: ignore[untyped-decorator]
    async def rebuild_with_feedback(self, state: BuildState, feedback: str) -> None:
        """Rebuild the user overview incorporating feedback, then persist."""
        self._state = state
        self._setup_trace(["plan-agent", "rebuild"])

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
