import asyncio
import json
import logging
from typing import Any

from langfuse import observe
from pydantic_ai import Agent
from pydantic_ai.models import Model

from flow44.ai.agents._base import BaseAgent, resolve_model
from flow44.ai.agents.plan.models import ArchitectureDesign, BuildState, DataSourceAnalysis, UserPlanOverview, UXDesign
from flow44.ai.agents.plan.prompts import (
    USER_PLAN_PROMPT,
    UX_DESIGN_PROMPT,
    render_architecture,
    render_data_source_analysis,
    render_user_plan,
)
from flow44.db.pending_plan import save_pending_plan
from flow44.integrations.flapi_api import data_source_client
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

# No global state needed - Agent instances created inline where used


async def _persist_state(state: BuildState) -> None:
    """Save BuildState to DB so it survives server restarts."""
    await save_pending_plan(state.project_id, state.model_dump_json())


class PlanAgent(BaseAgent):
    """Handles design and planning phases. Persists state to DB for ExecuteAgent."""

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        *,
        model: str | None = None,
        data_source_authorization: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, model=model)
        self.state = BuildState(project_id=self.project_id, model=self.model)
        self._data_source_authorization = data_source_authorization

    @observe(name="plan-agent-run")
    async def run(self, content: str, data_source_ids: list[str] | None = None) -> None:
        self.state.user_content = content
        self.state.data_source_ids = data_source_ids or []

        model = resolve_model(self.model)

        # Fetch data source metadata
        if self.state.data_source_ids:
            await self.emit({"type": "phase", "phase": "fetching_data_sources"})
            try:
                results = await asyncio.gather(
                    *[self._fetch_and_analyze_data_source(sid, model) for sid in self.state.data_source_ids]
                )
            except Exception:
                await self.emit(
                    {"type": "error", "message": "Build aborted: failed to fetch required data source data."}
                )
                await self.emit({"type": "phase", "phase": "idle"})
                return
            self.state.data_source_contexts = [ctx for ctx in results if ctx is not None]

            if self.state.data_source_contexts:
                from flow44.db.project import update_project_data_sources  # noqa: PLC0415

                await update_project_data_sources(self.project_id, self.state.data_source_contexts)
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
                            for ctx in self.state.data_source_contexts
                        ],
                    }
                )

        # Design (parallel)
        await self.emit({"type": "phase", "phase": "designing"})
        self.state.architecture, self.state.ux_design = await asyncio.gather(
            self._design_architecture(model),
            self._design_ux(model),
        )

        # Build user overview
        await self.emit({"type": "phase", "phase": "planning"})
        self.state.user_overview = await self._build_user_overview(model)

        # Persist to DB and present for approval
        self.state.phase = "awaiting_approval"
        await _persist_state(self.state)
        await self.emit({"type": "phase", "phase": "awaiting_approval"})
        await self.emit({"type": "plan_overview", "overview": self.state.user_overview.model_dump()})

    async def rebuild_with_feedback(self, feedback: str) -> None:
        """Rebuild the user overview incorporating feedback, then persist."""
        model = resolve_model(self.model)
        await self.emit({"type": "phase", "phase": "planning"})

        plan_input = json.dumps(
            {
                "user_request": self.state.user_content,
                "architecture": self.state.architecture.model_dump(),
                "ux_design": self.state.ux_design.model_dump(),
                "previous_overview": self.state.user_overview.model_dump(),
                "user_feedback": feedback,
            },
            indent=2,
        )
        agent = Agent(output_type=UserPlanOverview)
        result = await agent.run(
            plan_input,
            instructions=render_user_plan(has_feedback=True),
            model=model,
        )
        self.state.user_overview = result.output

        self.state.phase = "awaiting_approval"
        await _persist_state(self.state)
        await self.emit({"type": "phase", "phase": "awaiting_approval"})
        await self.emit({"type": "plan_overview", "overview": self.state.user_overview.model_dump()})

    # -- Design --

    async def _fetch_and_analyze_data_source(self, data_source_id: str, model: Model) -> dict[str, Any]:
        ds_name, sample_data = await data_source_client.fetch_data_source(
            data_source_id,
            authorization=self._data_source_authorization,
        )
        analysis = await self._analyze_data_source(ds_name, sample_data, model)
        return {
            "data_source_id": data_source_id,
            "data_source_name": ds_name,
            "sample_data": sample_data,
            **analysis,
        }

    async def _analyze_data_source(self, ds_name: str, sample_data: Any, model: Model) -> dict[str, Any]:
        prompt = render_data_source_analysis(
            user_content=self.state.user_content,
            data_source_name=ds_name,
            sample_data=sample_data,
        )
        try:
            agent = Agent(output_type=DataSourceAnalysis)
            result = await agent.run(
                "Analyze this data source.",
                instructions=prompt,
                model=model,
            )
            return result.output.model_dump()
        except Exception:
            logger.exception("[plan] Data source analysis failed, using degraded result")
            return {
                "data_schema": "Unable to analyze — see raw sample data",
                "relevant_fields": "See raw data",
                "data_characteristics": "Fetched from API",
                "integration_notes": f"Data preview: {json.dumps(sample_data, indent=2)[:500]}",
            }

    @observe(name="design-architecture")
    async def _design_architecture(self, model: Model) -> ArchitectureDesign:
        prompt = render_architecture(data_source_contexts=self.state.data_source_contexts or None)
        try:
            agent = Agent(output_type=ArchitectureDesign)
            result = await agent.run(
                self.state.user_content,
                instructions=prompt,
                model=model,
            )
            await self.emit({"type": "design_progress", "stream": "architecture", "content": "complete"})
            return result.output
        except Exception:
            logger.exception("[plan] Architecture design failed")
            await self.emit({"type": "design_progress", "stream": "architecture", "content": "failed"})
            return ArchitectureDesign()

    @observe(name="design-ux")
    async def _design_ux(self, model: Model) -> UXDesign:
        try:
            agent = Agent(output_type=UXDesign)
            result = await agent.run(
                self.state.user_content,
                instructions=UX_DESIGN_PROMPT,
                model=model,
            )
            await self.emit({"type": "design_progress", "stream": "ux", "content": "complete"})
            return result.output
        except Exception:
            logger.exception("[plan] UX design failed")
            await self.emit({"type": "design_progress", "stream": "ux", "content": "failed"})
            return UXDesign()

    @observe(name="build-user-overview")
    async def _build_user_overview(self, model: Model) -> UserPlanOverview:
        plan_input = json.dumps(
            {
                "user_request": self.state.user_content,
                "architecture": self.state.architecture.model_dump(),
                "ux_design": self.state.ux_design.model_dump(),
            },
            indent=2,
        )
        agent = Agent(output_type=UserPlanOverview)
        result = await agent.run(
            plan_input,
            instructions=USER_PLAN_PROMPT,
            model=model,
        )
        return result.output
