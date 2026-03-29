import asyncio
import json
import logging
import uuid
from typing import Any

from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.agents.execute.models import Task, WorkPlan
from flow44.ai.agents.execute.prompts import (
    SUMMARY_PROMPT,
    render_codegen,
    render_fix_errors,
    render_merge,
)
from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat, stream_chat
from flow44.ai.helpers import parse_json_response
from flow44.ai.parser import ActionParser
from flow44.ai.state import BuildState
from flow44.db.project import update_project_summary
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 2


class ExecuteAgent(BaseAgent):
    """Receives an approved plan and executes it using Flow orchestration."""

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        state: BuildState,
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, model=model, trace_id=trace_id)
        self._build_state = state
        self._flow = self._build_flow()

    def _build_flow(self) -> Flow[ExecutionState]:
        """Build the execution flow with explicit steps and routing."""
        flow = Flow[ExecutionState]("execute")

        flow.add_step("build_plan", self._step_build_plan, next_step="execute_tasks")
        flow.add_step("execute_tasks", self._step_execute_tasks, next_step="validate")
        flow.add_step("validate", self._step_validate, next_step=self._route_after_validate)
        flow.add_step("fix_errors", self._step_fix_errors, next_step="validate")
        flow.add_step("summarize", self._step_summarize, next_step=None)

        return flow

    def _route_after_validate(self, state: ExecutionState) -> str | None:
        """Route after validation: fix_errors, summarize, or give up."""
        if not state.all_errors:
            return "summarize"

        if state.fix_attempts >= MAX_FIX_ATTEMPTS:
            logger.warning("[execute] Max fix attempts reached, proceeding to summary")
            return "summarize"

        return "fix_errors"

    @observe(name="execute-agent-run")  # type: ignore[untyped-decorator]
    async def run(self) -> None:
        """Run the execution flow."""
        self._trace_id = langfuse_context.get_current_trace_id()
        langfuse_context.update_current_trace(
            session_id=self.project_id,
            user_id=self.project_id,
            metadata={"model": self.model or "default"},
            tags=["execute-agent"],
        )

        # Emit plan accepted
        await self.emit({"type": "plan_accepted", "overview": self._build_state.user_overview.model_dump()})

        # Initialize execution state
        exec_state = ExecutionState(
            build_state=self._build_state,
            project_id=self.project_id,
            sandbox_ref=self.sandbox,
            emit_fn=self.emit,
            model=self.model,
            trace_id=self._trace_id,
            langfuse_client=Langfuse(),
            llm_metadata_fn=self._llm_metadata,
        )

        # Run the flow
        final_state = await self._flow.run(exec_state, start="build_plan")

        # Final cleanup
        final_state.build_state.phase = "idle"
        final_state.build_state.work_plan = None
        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})

    # -- Flow Steps --

    async def _step_build_plan(self, state: ExecutionState) -> ExecutionState:
        """Step: Build technical plan from user overview."""
        await state.emit_fn({"type": "phase", "phase": "planning"})

        span = state.langfuse_client.span(trace_id=state.trace_id, name="build-technical-plan")
        state.observation_id = span.id

        try:
            state.build_state.work_plan = await self._build_technical_plan(state)

            await state.emit_fn(
                {
                    "type": "task_list",
                    "tasks": [
                        {"id": t.id, "title": t.title, "status": t.status}
                        for t in state.build_state.work_plan.tasks
                    ],
                }
            )
        finally:
            span.end()

        return state

    async def _step_execute_tasks(self, state: ExecutionState) -> ExecutionState:
        """Step: Execute all tasks in parallel layers."""
        if state.build_state.work_plan is None:
            raise RuntimeError("No work plan available")

        span = state.langfuse_client.span(
            trace_id=state.trace_id,
            name="execute-plan",
            metadata={
                "total_tasks": len(state.build_state.work_plan.tasks),
                "execution_layers": len(state.build_state.work_plan.execution_layers()),
            },
        )
        state.observation_id = span.id

        try:
            await state.emit_fn({"type": "phase", "phase": "executing"})

            state.build_state.completed_files = {}
            state.build_state.task_files = {}

            for layer in state.build_state.work_plan.execution_layers():
                await asyncio.gather(*[self._execute_task(t, state) for t in layer])
        finally:
            span.end()

        return state

    async def _step_validate(self, state: ExecutionState) -> ExecutionState:
        """Step: Validate with typecheck and build."""
        state.typecheck_errors, state.build_errors = await asyncio.gather(
            self._typecheck(state),
            self._build(state),
        )

        all_errors = []
        if state.typecheck_errors:
            all_errors.append("## TypeScript Errors\n" + state.typecheck_errors)
        if state.build_errors:
            all_errors.append("## Build Errors\n" + state.build_errors)

        state.all_errors = "\n\n".join(all_errors)
        return state

    async def _step_fix_errors(self, state: ExecutionState) -> ExecutionState:
        """Step: Auto-fix validation errors."""
        await state.emit_fn({"type": "phase", "phase": "fixing"})
        state.fix_attempts += 1

        prompt = render_fix_errors(errors=state.all_errors, files=state.build_state.completed_files)
        try:
            generated: list[tuple[str, str]] = []
            parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

            async for chunk in stream_chat(
                [Message.user("Fix the TypeScript errors.")],
                prompt,
                model=state.model,
                metadata=state.llm_metadata_fn("fix_errors"),
            ):
                parser.feed(chunk)
            parser.flush()

            for path, content in generated:
                await state.sandbox_ref.write_file(path, content)
                state.build_state.completed_files[path] = content
                await state.emit_fn({"type": "file", "path": path, "content": content})
        except Exception:
            logger.exception("[execute] Error fix pass failed")

        return state

    async def _step_summarize(self, state: ExecutionState) -> ExecutionState:
        """Step: Generate project summary."""
        span = state.langfuse_client.span(trace_id=state.trace_id, name="generate-summary")
        state.observation_id = span.id

        try:
            summary_input = json.dumps(
                {
                    "user_request": state.build_state.user_content,
                    "architecture": state.build_state.architecture.model_dump(),
                    "files_created": list(state.build_state.completed_files.keys()),
                },
                indent=2,
            )
            raw = await complete_chat(
                [Message.user(summary_input)],
                SUMMARY_PROMPT,
                model=state.model,
                metadata=state.llm_metadata_fn("generate_summary"),
            )
            summary_data = parse_json_response(raw)
            if summary_data:
                await update_project_summary(state.project_id, json.dumps(summary_data, ensure_ascii=False))
                await state.emit_fn({"type": "project_summary", "summary": summary_data})
        except Exception:
            logger.exception("[execute] Summary generation failed")
        finally:
            span.end()

        return state

    # -- Helper Methods --

    async def _build_technical_plan(self, state: ExecutionState) -> WorkPlan:
        """Build technical task plan from user overview."""
        merge_data: dict[str, object] = {
            "user_request": state.build_state.user_content,
            "architecture": state.build_state.architecture.model_dump(),
            "ux_design": state.build_state.ux_design.model_dump(),
            "user_preferences": [d.model_dump() for d in state.build_state.user_overview.decisions],
        }
        if state.build_state.data_source_contexts:
            merge_data["data_source_integrations"] = [
                {
                    k: ctx[k]
                    for k in (
                        "data_source_id",
                        "data_source_name",
                        "data_schema",
                        "relevant_fields",
                        "data_characteristics",
                        "integration_notes",
                    )
                }
                for ctx in state.build_state.data_source_contexts
            ]

        raw = await complete_chat(
            [Message.user(json.dumps(merge_data, indent=2))],
            render_merge(has_data_sources=bool(state.build_state.data_source_contexts)),
            model=state.model,
            metadata=state.llm_metadata_fn("build_technical_plan"),
        )
        plan_data = parse_json_response(raw)

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
            architecture=state.build_state.architecture,
            ux_design=state.build_state.ux_design,
            tasks=tasks,
        )

    async def _execute_task(self, task: Task, state: ExecutionState) -> None:
        """Execute a single task with Langfuse span."""
        if state.build_state.work_plan is None:
            raise RuntimeError("No work plan available")

        span = state.langfuse_client.span(
            trace_id=state.trace_id,
            parent_observation_id=state.observation_id,
            name=f"execute-task-{task.id}",
            metadata={"task_id": task.id, "task_title": task.title, "expected_files": len(task.files)},
        )

        try:
            task.status = "running"
            await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "running"})

            dep_paths: set[str] = set()
            for dep_id in task.depends_on:
                dep_paths.update(state.build_state.task_files.get(dep_id, []))

            prompt = render_codegen(
                task_title=task.title,
                task_description=task.description,
                task_files=task.files,
                architecture=state.build_state.work_plan.architecture.model_dump(),
                ux_design=state.build_state.work_plan.ux_design.model_dump(),
                dependency_files={p: c for p, c in state.build_state.completed_files.items() if p in dep_paths}
                or None,
                other_completed_files={p: c for p, c in state.build_state.completed_files.items() if p not in dep_paths}
                or None,
                data_source_contexts=state.build_state.data_source_contexts or None,
            )

            generated: list[tuple[str, str]] = []
            parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

            async for chunk in stream_chat(
                [Message.user("Generate the code.")],
                prompt,
                model=state.model,
                metadata=state.llm_metadata_fn(f"execute_task_{task.id}"),
            ):
                parser.feed(chunk)
            parser.flush()

            paths: list[str] = []
            for path, content in generated:
                await state.sandbox_ref.write_file(path, content)
                state.build_state.completed_files[path] = content
                paths.append(path)
                await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "running", "file": path})
                await state.emit_fn({"type": "file", "path": path, "content": content})

            state.build_state.task_files[task.id] = paths
            task.status = "completed"
            await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "completed"})
        except Exception as exc:
            logger.exception("[execute] Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
            await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "failed"})
        finally:
            span.end()

    async def _typecheck(self, state: ExecutionState) -> str:
        """Run TypeScript typecheck."""
        result = await state.sandbox_ref.run_build_command("npx tsc --noEmit")
        return result.errors

    async def _build(self, state: ExecutionState) -> str:
        """Run build command."""
        result = await state.sandbox_ref.run_build_command("pnpm build")
        return result.errors
