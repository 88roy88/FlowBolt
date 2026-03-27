import asyncio
import json
import logging
import uuid

from langfuse import observe
from pydantic_ai import Agent

from flow44.ai.agents.execute.parser import ActionParser
from flow44.ai.agents.execute.prompts import SUMMARY_PROMPT, render_codegen, render_fix_errors, render_merge
from flow44.ai.agents.execute.models import ProjectSummary, Task, WorkPlan
from flow44.ai.agents.plan.models import BuildState
from flow44.db.project import update_project_summary
from flow44.sandbox.main import PnpmSandbox

from flow44.ai.agents._base import BaseAgent, resolve_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# pydantic-ai agents
# ---------------------------------------------------------------------------

_plan_agent: Agent[None, None] = Agent()  # raw text for work plan JSON
_codegen_agent: Agent[None, str] = Agent()
_summary_agent: Agent[None, ProjectSummary] = Agent(output_type=ProjectSummary)


class ExecuteAgent(BaseAgent):
    """Receives an approved plan and executes it: build technical plan, generate code, validate, summarize."""

    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        state: BuildState,
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, model=model)
        self._state = state

    @observe(name="execute-agent-run")  # type: ignore[untyped-decorator]
    async def run(self) -> None:
        model = resolve_model(self.model)

        await self.emit({"type": "plan_accepted", "overview": self._state.user_overview.model_dump()})

        # Build technical plan
        await self.emit({"type": "phase", "phase": "planning"})
        self._state.work_plan = await self._build_technical_plan(model)

        await self.emit(
            {
                "type": "task_list",
                "tasks": [{"id": t.id, "title": t.title, "status": t.status} for t in self._state.work_plan.tasks],
            }
        )

        # Execute
        await self.emit({"type": "phase", "phase": "executing"})
        await self._execute(model)

        # Summary
        await self._generate_summary(model)

        self._state.phase = "idle"
        self._state.work_plan = None
        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})

    # -- Planning --

    @observe(name="build-technical-plan")  # type: ignore[untyped-decorator]
    async def _build_technical_plan(self, model: str | None) -> WorkPlan:
        merge_data: dict[str, object] = {
            "user_request": self._state.user_content,
            "architecture": self._state.architecture.model_dump(),
            "ux_design": self._state.ux_design.model_dump(),
            "user_preferences": [d.model_dump() for d in self._state.user_overview.decisions],
        }
        if self._state.data_source_contexts:
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
                for ctx in self._state.data_source_contexts
            ]

        result = await _plan_agent.run(
            json.dumps(merge_data, indent=2),
            instructions=render_merge(has_data_sources=bool(self._state.data_source_contexts)),
            model=model,
        )
        print("Plan agent output:\n", result.output)

        plan_data = json.loads(result.output.removeprefix("```json").removesuffix("```")) if isinstance(result.output, str) else {}

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
            architecture=self._state.architecture,
            ux_design=self._state.ux_design,
            tasks=tasks,
        )

    # -- Execution --

    async def _execute(self, model: str | None) -> None:
        if self._state.work_plan is None:
            raise RuntimeError("No work plan available")

        self._state.completed_files = {}
        self._state.task_files = {}

        for layer in self._state.work_plan.execution_layers():
            await asyncio.gather(*[self._execute_task(t, model) for t in layer])

        typecheck_errors, build_errors = await asyncio.gather(
            self._typecheck(),
            self._build(),
        )

        all_errors = []
        if typecheck_errors:
            all_errors.append("## TypeScript Errors\n" + typecheck_errors)
        if build_errors:
            all_errors.append("## Build Errors\n" + build_errors)
        if all_errors:
            await self._fix_errors("\n\n".join(all_errors), model)

    async def _execute_task(self, task: Task, model: str | None) -> None:
        if self._state.work_plan is None:
            raise RuntimeError("No work plan available")

        task.status = "running"
        await self.emit({"type": "task_update", "taskId": task.id, "status": "running"})

        dep_paths: set[str] = set()
        for dep_id in task.depends_on:
            dep_paths.update(self._state.task_files.get(dep_id, []))

        prompt = render_codegen(
            task_title=task.title,
            task_description=task.description,
            task_files=task.files,
            architecture=self._state.work_plan.architecture.model_dump(),
            ux_design=self._state.work_plan.ux_design.model_dump(),
            dependency_files={p: c for p, c in self._state.completed_files.items() if p in dep_paths} or None,
            other_completed_files={p: c for p, c in self._state.completed_files.items() if p not in dep_paths} or None,
            data_source_contexts=self._state.data_source_contexts or None,
        )

        try:
            generated: list[tuple[str, str]] = []
            parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

            async with _codegen_agent.run_stream(
                "Generate the code.",
                instructions=prompt,
                model=model,
            ) as stream:
                async for chunk in stream.stream_text(delta=True):
                    parser.feed(chunk)
            parser.flush()

            paths: list[str] = []
            for path, content in generated:
                await self.sandbox.write_file(path, content)
                self._state.completed_files[path] = content
                paths.append(path)
                await self.emit({"type": "task_update", "taskId": task.id, "status": "running", "file": path})
                await self.emit({"type": "file", "path": path, "content": content})

            self._state.task_files[task.id] = paths
            task.status = "completed"
            await self.emit({"type": "task_update", "taskId": task.id, "status": "completed"})
        except Exception as exc:
            logger.exception("[execute] Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
            await self.emit({"type": "task_update", "taskId": task.id, "status": "failed"})

    async def _typecheck(self) -> str:
        result = await self.sandbox.run_build_command("npx tsc --noEmit")
        return result.errors

    async def _build(self) -> str:
        result = await self.sandbox.run_build_command("pnpm build")
        return result.errors

    @observe(name="fix-errors-auto")  # type: ignore[untyped-decorator]
    async def _fix_errors(self, errors: str, model: str | None) -> None:
        await self.emit({"type": "phase", "phase": "fixing"})
        prompt = render_fix_errors(errors=errors, files=self._state.completed_files)
        try:
            generated: list[tuple[str, str]] = []
            parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

            async with _codegen_agent.run_stream(
                "Fix the TypeScript errors.",
                instructions=prompt,
                model=model,
            ) as stream:
                async for chunk in stream.stream_text(delta=True):
                    parser.feed(chunk)
            parser.flush()

            for path, content in generated:
                await self.sandbox.write_file(path, content)
                self._state.completed_files[path] = content
                await self.emit({"type": "file", "path": path, "content": content})
        except Exception:
            logger.exception("[execute] Error fix pass failed")

    # -- Summary --

    async def _generate_summary(self, model: str | None) -> None:
        try:
            summary_input = json.dumps(
                {
                    "user_request": self._state.user_content,
                    "architecture": self._state.architecture.model_dump(),
                    "files_created": list(self._state.completed_files.keys()),
                },
                indent=2,
            )
            result = await _summary_agent.run(
                summary_input,
                instructions=SUMMARY_PROMPT,
                model=model,
            )
            summary_data = result.output.model_dump()
            if summary_data:
                await update_project_summary(self.project_id, json.dumps(summary_data, ensure_ascii=False))
                await self.emit({"type": "project_summary", "summary": summary_data})
        except Exception:
            logger.exception("[execute] Summary generation failed")
