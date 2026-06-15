import asyncio
import json
import logging
import uuid

from langfuse import Langfuse
from langfuse.decorators import observe
from pydantic import ValidationError

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.execute.execution_state import ExecutionState
from flow44.ai.agents.execute.models import Task, WorkPlan
from flow44.ai.agents.execute.optional_packages import (
    OptionalPackageDecision,
    allowed_import_names,
    high_confidence_optional_package_decision,
    merge_optional_package_decisions,
    package_capabilities,
    package_install_names,
    repair_unselected_package_references,
    selected_package_names,
    validate_optional_package_decision,
)
from flow44.ai.agents.execute.prompts import (
    SUMMARY_PROMPT,
    render_codegen,
    render_fix_errors,
    render_merge,
    render_package_decision,
)
from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat, stream_chat
from flow44.ai.generated_app_contract import (
    GeneratedAppContractError,
    assert_generated_app_file_allowed,
    assert_generated_code_contract,
)
from flow44.ai.helpers import parse_json_response
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
        if not state.all_errors:
            return "summarize"

        if state.fix_attempts >= MAX_FIX_ATTEMPTS:
            logger.warning("[execute] Max fix attempts reached, proceeding to summary")
            return "summarize"

        return "fix_errors"

    @observe(name="execute-agent-run")  # type: ignore[untyped-decorator]
    async def run(self) -> None:
        """Run the execution flow."""
        self._setup_trace(["execute-agent"])

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
                        {"id": t.id, "title": t.title, "status": t.status} for t in state.build_state.work_plan.tasks
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

        await state.sandbox_ref.enable_optional_packages(
            package_install_names(state.build_state.work_plan.selected_packages)
        )
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

            # Pre-populate with deterministically generated data source files
            state.build_state.completed_files = dict(state.build_state.generated_data_source_files)
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

        selected_packages = state.build_state.work_plan.selected_packages if state.build_state.work_plan else []
        await state.sandbox_ref.enable_optional_packages(package_install_names(selected_packages))
        prompt = render_fix_errors(
            errors=state.all_errors,
            files=state.build_state.completed_files,
            selected_packages=selected_packages,
        )
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

            validated = [
                (assert_generated_code_contract(path, content, allowed_import_names(selected_packages)), content)
                for path, content in generated
            ]
            for path, content in validated:
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
        decision = await self._decide_optional_packages(state)
        selected_packages = selected_package_names(decision)
        await state.sandbox_ref.enable_optional_packages(package_install_names(selected_packages))

        merge_data: dict[str, object] = {
            "user_request": state.build_state.user_content,
            "architecture": state.build_state.architecture.model_dump(),
            "ux_design": state.build_state.ux_design.model_dump(),
            "user_preferences": [d.model_dump() for d in state.build_state.user_overview.decisions],
            "optional_package_decision": {
                "selected_packages": [package.model_dump() for package in decision.selected_packages],
                "selected_capabilities": package_capabilities(selected_packages),
            },
        }
        if state.build_state.data_source_contexts:
            merge_data["data_source_integrations"] = [
                {
                    k: ctx[k]
                    for k in (
                        "data_source_id",
                        "data_source_name",
                        "sanitized_name",
                        "relevant_fields",
                        "data_characteristics",
                        "integration_notes",
                        "param_ux_hints",
                        "params_info",
                        "can_run_without_input",
                    )
                    if k in ctx
                }
                for ctx in state.build_state.data_source_contexts
            ]

        raw = await complete_chat(
            [Message.user(json.dumps(merge_data, indent=2))],
            render_merge(
                has_data_sources=bool(state.build_state.data_source_contexts),
                selected_packages=selected_packages,
            ),
            model=state.model,
            metadata=state.llm_metadata_fn("build_technical_plan"),
        )
        plan_data = parse_json_response(raw)

        tasks: list[Task] = []
        for task_data in plan_data.get("tasks", []):
            safe_files: list[str] = []
            for path in task_data.get("files", []):
                try:
                    safe_files.append(assert_generated_app_file_allowed(path))
                except GeneratedAppContractError:
                    logger.warning("[execute] Dropping protected file from generated plan: %s", path)
            if not safe_files:
                continue
            tasks.append(
                Task(
                    id=task_data.get("id", f"task-{uuid.uuid4().hex[:6]}"),
                    title=repair_unselected_package_references(
                        task_data.get("title", "Untitled task"), selected_packages
                    ),
                    description=repair_unselected_package_references(
                        task_data.get("description", ""), selected_packages
                    ),
                    files=safe_files,
                    depends_on=task_data.get("depends_on", []),
                )
            )

        task_ids = {task.id for task in tasks}
        for task in tasks:
            task.depends_on = [dependency for dependency in task.depends_on if dependency in task_ids]

        return WorkPlan(
            id=f"plan-{uuid.uuid4().hex[:8]}",
            summary=repair_unselected_package_references(plan_data.get("summary", ""), selected_packages),
            architecture=state.build_state.architecture,
            ux_design=state.build_state.ux_design,
            tasks=tasks,
            selected_packages=selected_packages,
        )

    async def _decide_optional_packages(self, state: ExecutionState) -> OptionalPackageDecision:
        decision_input = json.dumps(
            {
                "user_request": state.build_state.user_content,
                "architecture": state.build_state.architecture.model_dump(),
                "ux_design": state.build_state.ux_design.model_dump(),
            },
            indent=2,
            ensure_ascii=False,
        )
        raw = await complete_chat(
            [Message.user(decision_input)],
            render_package_decision(),
            model=state.model,
            metadata=state.llm_metadata_fn("decide_optional_packages"),
        )
        try:
            decision = OptionalPackageDecision.model_validate(parse_json_response(raw))
            return merge_optional_package_decisions(
                validate_optional_package_decision(decision),
                high_confidence_optional_package_decision(state.build_state.user_content),
            )
        except ValidationError:
            logger.warning("[execute] Invalid optional package decision; using high-confidence package signals")
            return high_confidence_optional_package_decision(state.build_state.user_content)

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
                dependency_files={p: c for p, c in state.build_state.completed_files.items() if p in dep_paths} or None,
                other_completed_files={p: c for p, c in state.build_state.completed_files.items() if p not in dep_paths}
                or None,
                data_source_contexts=state.build_state.data_source_contexts or None,
                selected_packages=state.build_state.work_plan.selected_packages,
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

            expected_paths = {assert_generated_app_file_allowed(path) for path in task.files}
            allowed_imports = allowed_import_names(state.build_state.work_plan.selected_packages)
            validated: list[tuple[str, str]] = []
            for path, content in generated:
                normalized_path = assert_generated_code_contract(path, content, allowed_imports)
                if normalized_path not in expected_paths:
                    raise GeneratedAppContractError(
                        f"Generated unexpected file outside task contract: {normalized_path}"
                    )
                validated.append((normalized_path, content))

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
        return str(result.errors)

    async def _build(self, state: ExecutionState) -> str:
        """Run build command."""
        result = await state.sandbox_ref.run_build_command("pnpm build")
        return str(result.errors)
