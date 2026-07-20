import asyncio
import json
import logging
import uuid
from typing import Any

from opik import Opik, opik_context, track

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.agents.execute.models import Task, WorkPlan
from flow44.ai.agents.execute.prompts import (
    SUMMARY_PROMPT,
    render_codegen,
    render_feedback,
    render_merge,
)
from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat, stream_chat
from flow44.ai.file_safety import (
    FileSafetyError,
    format_rejection_feedback,
    screen_generated_files,
)
from flow44.ai.helpers import format_agent_feedback, parse_json_response
from flow44.ai.parser import ActionParser
from flow44.ai.state import BuildState
from flow44.db.project import update_project_summary
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)

MAX_FIX_ATTEMPTS = 10


class ExecuteAgent(BaseAgent):
    """Receives an approved plan and executes it using Flow orchestration."""

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        state: BuildState,
        *,
        user_id: str,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, user_id, model=model, trace_id=trace_id)
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
        if not state.all_errors and not state.rejected_files:
            return "summarize"

        if state.fix_attempts >= MAX_FIX_ATTEMPTS:
            logger.warning("[execute] Max fix attempts reached, proceeding to summary")
            return "summarize"

        return "fix_errors"

    @track(name="execute-agent-run")  # type: ignore[untyped-decorator]
    async def run(self) -> None:
        """Run the execution flow."""
        self._setup_trace(["execute-agent"])

        # Emit plan accepted
        await self.emit({"type": "plan_accepted", "overview": self._build_state.user_overview.model_dump()})

        # Initialize execution state
        current_span = opik_context.get_current_span_data()
        exec_state = ExecutionState(
            build_state=self._build_state,
            project_id=self.project_id,
            sandbox_ref=self.sandbox,
            emit_fn=self.emit,
            model=self.model,
            trace_id=self._trace_id,
            root_span_id=current_span.id if current_span else None,
            opik_client=Opik(),
            llm_metadata_fn=self._llm_metadata,
        )

        # Run the flow
        final_state = await self._flow.run(exec_state, start="build_plan")

        self._set_trace_output(
            {
                "files_written": list(final_state.build_state.completed_files.keys()),
                "fix_attempts": final_state.fix_attempts,
                "rejected_files": [str(r) for r in final_state.rejected_files],
            }
        )

        # Final cleanup
        final_state.build_state.phase = "idle"
        final_state.build_state.work_plan = None
        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})

    # -- Flow Steps --

    async def _step_build_plan(self, state: ExecutionState) -> ExecutionState:
        """Step: Build technical plan from user overview."""
        await state.emit_fn({"type": "phase", "phase": "planning"})

        span = state.opik_client.span(
            trace_id=state.trace_id,
            parent_span_id=state.root_span_id,
            name="build-technical-plan",
            input={"user_request": state.build_state.user_content},
        )
        state.observation_id = span.id

        try:
            state.build_state.work_plan = await self._build_technical_plan(state)

            await state.emit_fn(
                {
                    "type": "task_list",
                    "tasks": [
                        {"id": t.id, "title": t.title, "status": t.status} for t in state.build_state.work_plan.tasks
                    ],
                }
            )
        except Exception as exc:
            span.end(error_info=self._error_info(exc))
            raise
        else:
            span.end(
                output={
                    "task_count": len(state.build_state.work_plan.tasks),
                    "tasks": [t.title for t in state.build_state.work_plan.tasks],
                }
            )

        return state

    async def _step_execute_tasks(self, state: ExecutionState) -> ExecutionState:
        """Step: Execute all tasks in parallel layers."""
        if state.build_state.work_plan is None:
            raise RuntimeError("No work plan available")

        span = state.opik_client.span(
            trace_id=state.trace_id,
            parent_span_id=state.root_span_id,
            name="execute-plan",
            input={"tasks": [t.title for t in state.build_state.work_plan.tasks]},
            metadata={
                "total_tasks": len(state.build_state.work_plan.tasks),
                "execution_layers": len(state.build_state.work_plan.execution_layers()),
            },
        )
        state.observation_id = span.id

        try:
            await state.emit_fn({"type": "phase", "phase": "executing"})

            # Pre-populate with deterministically generated data source files
            state.build_state.completed_files = dict(state.build_state.generated_data_source_files)
            state.build_state.task_files = {}

            for layer in state.build_state.work_plan.execution_layers():
                await asyncio.gather(*[self._execute_task(t, state) for t in layer])
        except Exception as exc:
            span.end(error_info=self._error_info(exc))
            raise
        else:
            failed_tasks = [t.title for t in state.build_state.work_plan.tasks if t.status == "failed"]
            span.end(
                output={
                    "files_written": list(state.build_state.completed_files.keys()),
                    "failed_tasks": failed_tasks,
                }
            )

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

        span = state.opik_client.span(
            trace_id=state.trace_id,
            parent_span_id=state.root_span_id,
            name="fix-errors",
            input={"errors": state.all_errors, "fix_attempt": state.fix_attempts},
        )
        state.observation_id = span.id

        prompt = render_feedback(files=state.build_state.completed_files)
        messages: list[dict[str, Any] | Message] = [
            Message.user(format_agent_feedback(state.all_errors, state.rejected_files))
        ]

        try:
            generated: list[tuple[str, str]] = []
            parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

            async for chunk in stream_chat(
                messages,
                prompt,
                model=state.model,
                metadata=state.llm_metadata_fn("fix_errors", parent_span_id=span.id),
            ):
                parser.feed(chunk)
            parser.flush()

            if generated:
                validated, state.rejected_files = screen_generated_files(generated)
                for path, content in validated:
                    await state.sandbox_ref.write_file(path, content)
                    state.build_state.completed_files[path] = content
                    await state.emit_fn({"type": "file", "path": path, "content": content})
        except Exception as exc:
            logger.exception("[execute] Error fix pass failed")
            span.end(error_info=self._error_info(exc))
        else:
            span.end(output={"files_fixed": [p for p, _ in generated]})

        return state

    async def _step_summarize(self, state: ExecutionState) -> ExecutionState:
        """Step: Generate project summary."""
        if state.rejected_files:
            await state.emit_fn({"type": "error", "message": format_rejection_feedback(state.rejected_files)})

        span = state.opik_client.span(
            trace_id=state.trace_id,
            parent_span_id=state.root_span_id,
            name="generate-summary",
            input={"files_created": list(state.build_state.completed_files.keys())},
        )
        state.observation_id = span.id

        summary_data = None
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
                metadata=state.llm_metadata_fn("generate_summary", parent_span_id=state.observation_id),
            )
            summary_data = parse_json_response(raw)
            if summary_data:
                overview = summary_data.get("file_overview")
                if isinstance(overview, dict):
                    summary_data["file_overview"] = {
                        path: desc for path, desc in overview.items() if path in state.build_state.completed_files
                    }
                await update_project_summary(state.project_id, json.dumps(summary_data, ensure_ascii=False))
                await state.emit_fn({"type": "project_summary", "summary": summary_data})
        except Exception as exc:
            logger.exception("[execute] Summary generation failed")
            span.end(error_info=self._error_info(exc))
        else:
            span.end(output=summary_data or {})

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
                    "data_source_id": ctx.data_source_id,
                    "data_source_name": ctx.data_source_name,
                    "sanitized_name": ctx.sanitized_name,
                    "relevant_fields": ctx.relevant_fields,
                    "data_characteristics": ctx.data_characteristics,
                    "integration_notes": ctx.integration_notes,
                    "param_ux_hints": ctx.param_ux_hints,
                    "params_info": ctx.params_info,
                    "can_run_without_input": ctx.can_run_without_input,
                }
                for ctx in state.build_state.data_source_contexts
            ]

        raw = await complete_chat(
            [Message.user(json.dumps(merge_data, indent=2))],
            render_merge(has_data_sources=bool(state.build_state.data_source_contexts)),
            model=state.model,
            metadata=state.llm_metadata_fn("build_technical_plan", parent_span_id=state.observation_id),
        )
        plan_data = parse_json_response(raw)

        tasks: list[Task] = [
            Task(
                id=task_data.get("id", f"task-{uuid.uuid4().hex[:6]}"),
                title=task_data.get("title", "Untitled task"),
                description=task_data.get("description", ""),
                files=task_data.get("files", []),
                depends_on=task_data.get("depends_on", []),
            )
            for task_data in plan_data.get("tasks", [])
        ]

        # TODO(#166): no plan-level guard here — have the planner revise dangling depends_on instead of dropping them
        task_ids = {task.id for task in tasks}
        for task in tasks:
            valid_dependencies = [dependency for dependency in task.depends_on if dependency in task_ids]
            if len(valid_dependencies) != len(task.depends_on):
                logger.warning(
                    "[execute] Dropping missing dependencies from generated task %s: %s",
                    task.id,
                    sorted(set(task.depends_on) - task_ids),
                )
            task.depends_on = valid_dependencies

        return WorkPlan(
            id=f"plan-{uuid.uuid4().hex[:8]}",
            summary=plan_data.get("summary", ""),
            architecture=state.build_state.architecture,
            ux_design=state.build_state.ux_design,
            tasks=tasks,
        )

    async def _execute_task(self, task: Task, state: ExecutionState) -> None:
        """Execute a single task with an Opik span."""
        if state.build_state.work_plan is None:
            raise RuntimeError("No work plan available")

        span = state.opik_client.span(
            trace_id=state.trace_id,
            parent_span_id=state.observation_id,
            name=f"execute-task-{task.id}",
            input={"task_title": task.title, "task_description": task.description, "expected_files": task.files},
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
                dependency_files={p: c for p, c in state.build_state.completed_files.items() if p in dep_paths} or None,
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
                metadata=state.llm_metadata_fn(f"execute_task_{task.id}", parent_span_id=span.id),
            ):
                parser.feed(chunk)
            parser.flush()

            expected_paths = set(task.files)
            safe, rejections = screen_generated_files(generated)
            validated: list[tuple[str, str]] = []
            for path, content in safe:
                if path not in expected_paths:
                    logger.warning("[execute] Dropping file outside task contract %s: %s", task.id, path)
                    rejections.append(FileSafetyError(f"File is outside the task contract: {path}"))
                    continue
                validated.append((path, content))
            if rejections:
                state.rejected_files.extend(rejections)

            paths: list[str] = []
            for path, content in validated:
                await state.sandbox_ref.write_file(path, content)
                state.build_state.completed_files[path] = content
                paths.append(path)
                await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "running", "file": path})
                await state.emit_fn({"type": "file", "path": path, "content": content})

            state.build_state.task_files[task.id] = paths
            task.status = "completed"
            await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "completed"})
            span.end(output={"files_written": paths, "rejected_files": [str(r) for r in rejections]})
        except Exception as exc:
            logger.exception("[execute] Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
            await state.emit_fn({"type": "task_update", "taskId": task.id, "status": "failed"})
            span.end(error_info=self._error_info(exc))

    async def _typecheck(self, state: ExecutionState) -> str:
        """Run TypeScript typecheck."""
        result = await state.sandbox_ref.run_build_command("npx tsc --noEmit")
        return str(result.errors)

    async def _build(self, state: ExecutionState) -> str:
        """Run build command."""
        result = await state.sandbox_ref.run_build_command("pnpm build")
        return str(result.errors)
