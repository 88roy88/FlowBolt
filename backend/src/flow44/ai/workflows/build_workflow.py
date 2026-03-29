"""Build workflow using pydantic-graph for explicit orchestration.

This replaces the implicit flow in the old BuildAgent with a clear DAG:
    DesignNode → PlanNode → [AWAIT APPROVAL] → ExecuteNode → ValidateNode
                                                                    ↓
                                                              FixErrorsNode
                                                                    ↓
                                                              ValidateNode → SummarizeNode → End
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from flow44.ai.agents._base import resolve_model
from pydantic_ai.models import Model
from flow44.ai.agents.execute.models import ProjectSummary, Task, WorkPlan
from flow44.ai.agents.execute.parser import ActionParser
from flow44.ai.agents.execute.prompts import SUMMARY_PROMPT, render_codegen, render_fix_errors, render_merge
from flow44.ai.agents.plan.models import ArchitectureDesign, BuildState, DataSourceAnalysis, UXDesign, UserPlanOverview
from flow44.ai.agents.plan.prompts import (
    USER_PLAN_PROMPT,
    UX_DESIGN_PROMPT,
    render_architecture,
    render_data_source_analysis,
    render_user_plan,
)
from flow44.db.pending_plan import delete_pending_plan, save_pending_plan
from flow44.db.project import update_project_summary
from flow44.integrations.flapi_api import data_source_client
from flow44.sandbox.main import PnpmSandbox
from langfuse import observe
from pydantic_ai import Agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured LLM call helper
# Uses pydantic-ai's Agent API for convenience (structured output, system prompt)
# but just for typed generation - no agent behavior
# ---------------------------------------------------------------------------


async def _generate_structured[T](
    output_type: type[T],
    user_prompt: str,
    system_prompt: str,
    model: Model,
) -> T:
    """Call LLM for structured output. Not an agent - just a typed generation call."""
    # We use Agent API for convenience (it handles structured output)
    # but this is conceptually just: model.call(prompt, schema) -> typed output
    agent = Agent(output_type=output_type)
    result = await agent.run(user_prompt, instructions=system_prompt, model=model)
    return result.output


async def _generate_architecture(user_request: str, data_source_contexts: list[dict[str, Any]] | None, model: Model) -> ArchitectureDesign:
    """Generate architecture design via LLM."""
    return await _generate_structured(
        ArchitectureDesign,
        user_request,
        render_architecture(data_source_contexts=data_source_contexts),
        model,
    )


async def _generate_ux_design(user_request: str, model: Model) -> UXDesign:
    """Generate UX design via LLM."""
    return await _generate_structured(UXDesign, user_request, UX_DESIGN_PROMPT, model)


async def _generate_plan_overview(user_request: str, architecture: ArchitectureDesign, ux_design: UXDesign, model: Model) -> UserPlanOverview:
    """Generate user-facing plan overview via LLM."""
    plan_input = json.dumps(
        {
            "user_request": user_request,
            "architecture": architecture.model_dump(),
            "ux_design": ux_design.model_dump(),
        },
        indent=2,
    )
    return await _generate_structured(UserPlanOverview, plan_input, USER_PLAN_PROMPT, model)


async def _analyze_data_source(user_content: str, ds_name: str, sample_data: Any, model: Model) -> dict[str, Any]:
    """Analyze data source structure and relevance via LLM."""
    prompt = render_data_source_analysis(user_content=user_content, data_source_name=ds_name, sample_data=sample_data)
    try:
        analysis = await _generate_structured(DataSourceAnalysis, "Analyze this data source.", prompt, model)
        return analysis.model_dump()
    except Exception:
        logger.exception("[workflow] Data source analysis failed")
        return {
            "data_schema": "Unable to analyze — see raw sample data",
            "relevant_fields": "See raw data",
            "data_characteristics": "Fetched from API",
            "integration_notes": f"Data preview: {json.dumps(sample_data, indent=2)[:500]}",
        }


# ---------------------------------------------------------------------------
# Deps: shared across all nodes
# ---------------------------------------------------------------------------


@dataclass
class BuildDeps:
    """Dependencies injected into every node in the graph."""

    sandbox: PnpmSandbox
    emit: Any  # Callable for SSE events
    model: Model  # Resolved model instance
    data_source_authorization: str | None = None


# ---------------------------------------------------------------------------
# Graph Nodes: Each step in the workflow
# ---------------------------------------------------------------------------


@dataclass
class DesignNode(BaseNode[BuildState, BuildDeps, None]):
    """Step 1: Design architecture + UX in parallel.

    This node uses pydantic-ai agents for structured output.
    """

    @observe(name="workflow-design")
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> PlanNode:
        await ctx.deps.emit({"type": "phase", "phase": "designing"})

        # Run architecture and UX design in parallel
        ctx.state.architecture, ctx.state.ux_design = await asyncio.gather(
            self._design_architecture(ctx),
            self._design_ux(ctx),
        )

        return PlanNode()

    async def _design_architecture(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> ArchitectureDesign:
        try:
            design = await _generate_architecture(
                ctx.state.user_content,
                ctx.state.data_source_contexts or None,
                ctx.deps.model,
            )
            await ctx.deps.emit({"type": "design_progress", "stream": "architecture", "content": "complete"})
            return design
        except Exception:
            logger.exception("[workflow] Architecture design failed")
            await ctx.deps.emit({"type": "design_progress", "stream": "architecture", "content": "failed"})
            return ArchitectureDesign()

    async def _design_ux(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> UXDesign:
        try:
            design = await _generate_ux_design(ctx.state.user_content, ctx.deps.model)
            await ctx.deps.emit({"type": "design_progress", "stream": "ux", "content": "complete"})
            return design
        except Exception:
            logger.exception("[workflow] UX design failed")
            await ctx.deps.emit({"type": "design_progress", "stream": "ux", "content": "failed"})
            return UXDesign()


@dataclass
class PlanNode(BaseNode[BuildState, BuildDeps, str]):
    """Step 2: Build user-facing plan overview.

    This is the plan that gets presented to the user for approval.
    The graph pauses here until user accepts/modifies/rejects.
    """

    @observe(name="workflow-plan")
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> End[str]:
        await ctx.deps.emit({"type": "phase", "phase": "planning"})

        ctx.state.user_overview = await _generate_plan_overview(
            ctx.state.user_content,
            ctx.state.architecture,
            ctx.state.ux_design,
            ctx.deps.model,
        )

        # Persist state to DB so ExecuteNode can resume later
        ctx.state.phase = "awaiting_approval"
        await save_pending_plan(ctx.state.project_id, ctx.state.model_dump_json())

        # Present plan and STOP - user must approve before continuing
        await ctx.deps.emit({"type": "phase", "phase": "awaiting_approval"})
        await ctx.deps.emit({"type": "plan_overview", "overview": ctx.state.user_overview.model_dump()})

        # Graph ends here - ExecuteNode will be started separately after approval
        return End("awaiting_approval")


@dataclass
class ExecuteNode(BaseNode[BuildState, BuildDeps, None]):
    """Step 3: Generate technical plan and execute tasks.

    This node starts AFTER user approval.
    It builds the detailed task plan and generates code for each task in parallel layers.
    """

    @observe(name="workflow-execute")
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> ValidateNode:
        await ctx.deps.emit({"type": "plan_accepted", "overview": ctx.state.user_overview.model_dump()})
        await ctx.deps.emit({"type": "phase", "phase": "planning"})

        # Build technical plan
        ctx.state.work_plan = await self._build_technical_plan(ctx)
        await ctx.deps.emit(
            {
                "type": "task_list",
                "tasks": [{"id": t.id, "title": t.title, "status": t.status} for t in ctx.state.work_plan.tasks],
            }
        )

        # Execute tasks
        await ctx.deps.emit({"type": "phase", "phase": "executing"})
        ctx.state.completed_files = {}
        ctx.state.task_files = {}

        for layer in ctx.state.work_plan.execution_layers():
            await asyncio.gather(*[self._execute_task(ctx, t) for t in layer])

        return ValidateNode()

    async def _build_technical_plan(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> WorkPlan:
        merge_data: dict[str, object] = {
            "user_request": ctx.state.user_content,
            "architecture": ctx.state.architecture.model_dump(),
            "ux_design": ctx.state.ux_design.model_dump(),
            "user_preferences": [d.model_dump() for d in ctx.state.user_overview.decisions],
        }
        if ctx.state.data_source_contexts:
            merge_data["data_source_integrations"] = [
                {
                    k: ctx_item[k]
                    for k in (
                        "data_source_id",
                        "data_source_name",
                        "data_schema",
                        "relevant_fields",
                        "data_characteristics",
                        "integration_notes",
                    )
                }
                for ctx_item in ctx.state.data_source_contexts
            ]

        agent = Agent[None, str]()
        result = await agent.run(
            json.dumps(merge_data, indent=2),
            instructions=render_merge(has_data_sources=bool(ctx.state.data_source_contexts)),
            model=ctx.deps.model,
        )

        plan_data = (
            json.loads(result.output.removeprefix("```json").removesuffix("```"))
            if isinstance(result.output, str)
            else {}
        )

        tasks = [
            Task(
                id=t.get("id", f"task-{uuid.uuid4().hex[:6]}"),
                title=t.get("title", "Untitled task"),
                description=t.get("description", ""),
                files=t.get("files", []),
                depends_on=t.get("depends_on", []),
            )
            for t in plan_data.get("tasks", [])
        ]

        return WorkPlan(
            id=f"plan-{uuid.uuid4().hex[:8]}",
            summary=plan_data.get("summary", ""),
            architecture=ctx.state.architecture,
            ux_design=ctx.state.ux_design,
            tasks=tasks,
        )

    async def _execute_task(self, ctx: GraphRunContext[BuildState, BuildDeps], task: Task) -> None:
        await ctx.deps.emit({"type": "task_update", "task_id": task.id, "status": "running"})

        # Prepare dependency files and other completed files
        dep_paths: set[str] = set()
        for dep_id in task.depends_on:
            dep_paths.update(ctx.state.task_files.get(dep_id, []))

        prompt = render_codegen(
            task_title=task.title,
            task_description=task.description,
            task_files=task.files,
            architecture=ctx.state.work_plan.architecture.model_dump(),
            ux_design=ctx.state.work_plan.ux_design.model_dump(),
            dependency_files={p: c for p, c in ctx.state.completed_files.items() if p in dep_paths} or None,
            other_completed_files={p: c for p, c in ctx.state.completed_files.items() if p not in dep_paths} or None,
            data_source_contexts=ctx.state.data_source_contexts or None,
        )

        # Use streaming to parse actions as they arrive
        generated: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

        agent = Agent[None, str]()
        async with agent.run_stream(
            f"Generate code for task: {task.title}",
            instructions=prompt,
            model=ctx.deps.model,
        ) as stream:
            async for chunk in stream.stream_text(delta=True):
                parser.feed(chunk)
        parser.flush()

        task_files: list[str] = []
        for path, content in generated:
            await ctx.deps.sandbox.write_file(path, content)
            ctx.state.completed_files[path] = content
            task_files.append(path)
            await ctx.deps.emit({"type": "file", "path": path, "content": content})

        ctx.state.task_files[task.id] = task_files
        task.status = "completed"
        await ctx.deps.emit({"type": "task_update", "task_id": task.id, "status": "completed"})


@dataclass
class ValidateNode(BaseNode[BuildState, BuildDeps, str]):
    """Step 4: Validate code (typecheck + build).

    Conditional branching:
    - No errors → SummarizeNode
    - Has errors + attempts < 3 → FixErrorsNode
    - Has errors + attempts >= 3 → End (failure)
    """

    async def run(
        self, ctx: GraphRunContext[BuildState, BuildDeps]
    ) -> SummarizeNode | FixErrorsNode | End[str]:
        # Run validation
        typecheck_errors, build_errors = await asyncio.gather(
            self._typecheck(ctx),
            self._build(ctx),
        )

        all_errors = []
        if typecheck_errors:
            all_errors.append("## TypeScript Errors\n" + typecheck_errors)
        if build_errors:
            all_errors.append("## Build Errors\n" + build_errors)

        if not all_errors:
            # Success! Move to summarize
            return SummarizeNode()

        # Has errors - check if we should retry
        ctx.state.validation_errors = "\n\n".join(all_errors)
        if ctx.state.fix_attempts >= 3:
            return End("build_failed_max_attempts")

        # Try to fix
        return FixErrorsNode()

    async def _typecheck(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> str:
        try:
            output_lines = []
            async for line in ctx.deps.sandbox.exec("npm run typecheck 2>&1"):
                output_lines.append(line)
            output = "".join(output_lines)
            return output if "error TS" in output else ""
        except Exception:
            logger.exception("[workflow] Typecheck failed")
            return ""

    async def _build(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> str:
        try:
            output_lines = []
            async for line in ctx.deps.sandbox.exec("npm run build 2>&1"):
                output_lines.append(line)
            output = "".join(output_lines)
            return output if ("error" in output.lower() or "failed" in output.lower()) else ""
        except Exception:
            logger.exception("[workflow] Build failed")
            return ""


@dataclass
class FixErrorsNode(BaseNode[BuildState, BuildDeps, None]):
    """Step 5: Fix validation errors using AI.

    This node uses a pydantic-ai agent to analyze errors and fix them.
    After fixing, it loops back to ValidateNode.
    """

    @observe(name="workflow-fix-errors")
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> ValidateNode:
        ctx.state.fix_attempts += 1
        await ctx.deps.emit(
            {
                "type": "phase",
                "phase": "fixing_errors",
                "attempt": ctx.state.fix_attempts,
            }
        )
        prompt = render_fix_errors(
            errors=ctx.state.validation_errors,
            files=ctx.state.completed_files,
        )

        # Use streaming parser
        generated: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

        agent = Agent[None, str]()
        async with agent.run_stream(
            "Fix the errors",
            instructions=prompt,
            model=ctx.deps.model,
        ) as stream:
            async for chunk in stream.stream_text(delta=True):
                parser.feed(chunk)
        parser.flush()

        for path, content in generated:
            await ctx.deps.sandbox.write_file(path, content)
            ctx.state.completed_files[path] = content
            await ctx.deps.emit({"type": "file", "path": path, "content": content})

        # Loop back to validation
        return ValidateNode()


@dataclass
class SummarizeNode(BaseNode[BuildState, BuildDeps, str]):
    """Step 6: Generate project summary.

    Final step - generates summary and ends the workflow.
    """

    @observe(name="workflow-summarize")
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> End[str]:
        summary_input = json.dumps(
            {
                "user_request": ctx.state.user_content,
                "architecture": ctx.state.architecture.model_dump(),
                "ux_design": ctx.state.ux_design.model_dump(),
                "files": list(ctx.state.completed_files.keys()),
            },
            indent=2,
        )

        agent = Agent(output_type=ProjectSummary)
        result = await agent.run(
            summary_input,
            instructions=SUMMARY_PROMPT,
            model=ctx.deps.model,
        )

        summary = result.output
        await update_project_summary(ctx.state.project_id, summary.model_dump_json())

        await ctx.deps.emit({"type": "phase", "phase": "complete"})
        await ctx.deps.emit({"type": "action_complete"})

        return End("build_complete")


# ---------------------------------------------------------------------------
# Workflow: The orchestrated graph
# ---------------------------------------------------------------------------


class BuildWorkflow:
    """Orchestrates the build process using pydantic-graph.

    Flow:
        DesignNode → PlanNode → [AWAIT APPROVAL]
                                      ↓
        [RESUME] → ExecuteNode → ValidateNode ⟲ FixErrorsNode
                                      ↓
                                SummarizeNode → End
    """

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        emit: Any,
        *,
        model: str | None = None,
        data_source_authorization: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.sandbox = sandbox
        self.emit = emit
        self.model = resolve_model(model)  # Resolve once at initialization
        self.data_source_authorization = data_source_authorization

        # Build the graph
        self._graph = Graph(
            nodes=[
                DesignNode,
                PlanNode,
                ExecuteNode,
                ValidateNode,
                FixErrorsNode,
                SummarizeNode,
            ]
        )

    async def run_design_and_plan(
        self,
        user_content: str,
        data_source_ids: list[str] | None = None,
    ) -> BuildState:
        """Run the design + plan phases (up to approval).

        Returns the BuildState which is persisted to DB.
        """
        state = BuildState(project_id=self.project_id, model=self.model)
        state.user_content = user_content
        state.data_source_ids = data_source_ids or []

        # Fetch data sources if needed
        if state.data_source_ids:
            await self.emit({"type": "phase", "phase": "fetching_data_sources"})
            try:
                results = await asyncio.gather(
                    *[self._fetch_and_analyze_data_source(sid, state) for sid in state.data_source_ids]
                )
                state.data_source_contexts = [ctx for ctx in results if ctx is not None]

                if state.data_source_contexts:
                    from flow44.db.project import update_project_data_sources  # noqa: PLC0415

                    await update_project_data_sources(self.project_id, state.data_source_contexts)
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
                                for ctx in state.data_source_contexts
                            ],
                        }
                    )
            except Exception:
                await self.emit(
                    {"type": "error", "message": "Build aborted: failed to fetch required data source data."}
                )
                await self.emit({"type": "phase", "phase": "idle"})
                raise

        # Run graph: DesignNode → PlanNode → End
        deps = BuildDeps(
            sandbox=self.sandbox,
            emit=self.emit,
            model=self.model,
            data_source_authorization=self.data_source_authorization,
        )
        result = await self._graph.run(DesignNode(), state=state, deps=deps)

        return result.state

    async def rebuild_plan_with_feedback(self, state: BuildState, feedback: str) -> BuildState:
        """Rebuild the plan overview with user feedback."""
        await self.emit({"type": "phase", "phase": "planning"})

        # Generate updated plan with feedback
        agent = Agent(output_type=UserPlanOverview)
        plan_input = json.dumps(
            {
                "user_request": state.user_content,
                "architecture": state.architecture.model_dump(),
                "ux_design": state.ux_design.model_dump(),
                "previous_overview": state.user_overview.model_dump(),
                "user_feedback": feedback,
            },
            indent=2,
        )
        result = await agent.run(
            plan_input,
            instructions=render_user_plan(has_feedback=True),
            model=self.model,
        )
        state.user_overview = result.output

        # Persist and present
        state.phase = "awaiting_approval"
        await save_pending_plan(state.project_id, state.model_dump_json())
        await self.emit({"type": "phase", "phase": "awaiting_approval"})
        await self.emit({"type": "plan_overview", "overview": state.user_overview.model_dump()})

        return state

    async def run_execution(self, state: BuildState) -> BuildState:
        """Run execution phase after approval.

        Runs: ExecuteNode → ValidateNode → [FixErrorsNode loop] → SummarizeNode → End
        """
        deps = BuildDeps(
            sandbox=self.sandbox,
            emit=self.emit,
            model=self.model,
            data_source_authorization=self.data_source_authorization,
        )

        # Clean up the pending plan
        await delete_pending_plan(state.project_id)

        # Resume from ExecuteNode
        result = await self._graph.run(ExecuteNode(), state=state, deps=deps)

        return result.state

    async def _fetch_and_analyze_data_source(self, data_source_id: str, state: BuildState) -> dict[str, Any]:
        ds_name, sample_data = await data_source_client.fetch_data_source(
            data_source_id,
            authorization=self.data_source_authorization,
        )

        analysis = await _analyze_data_source(state.user_content, ds_name, sample_data, self.model)

        return {
            "data_source_id": data_source_id,
            "data_source_name": ds_name,
            "sample_data": sample_data,
            **analysis,
        }
