import asyncio
import json
import logging
import uuid
from typing import Any

from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.execute.prompts import (
    SUMMARY_PROMPT,
    render_codegen,
    render_fix_errors,
    render_merge,
)
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import complete_chat, stream_chat
from flow44.ai.helpers import parse_json_response
from flow44.ai.parser import ActionParser
from flow44.ai.state import BuildState
from flow44.ai.task_tree import Task, WorkPlan
from flow44.db.project import update_project_summary
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)


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
        super().__init__(project_id, sandbox, model=model, trace_id=trace_id)
        self._state = state
        self._observation_id: str | None = None

    @observe(name="execute-agent-run")  # type: ignore[untyped-decorator]
    async def run(self) -> None:
        self._trace_id = langfuse_context.get_current_trace_id()

        langfuse_context.update_current_trace(
            session_id=self.project_id,
            user_id=self.project_id,
            metadata={"model": self.model or "default"},
            tags=["execute-agent"],
        )

        await self.emit({"type": "plan_accepted", "overview": self._state.user_overview.model_dump()})
        langfuse_client = Langfuse()

        # Build technical plan
        await self.emit({"type": "phase", "phase": "planning"})
        span_plan = langfuse_client.span(trace_id=self._trace_id, name="build-technical-plan")
        self._observation_id = span_plan.id
        self._state.work_plan = await self._build_technical_plan()
        span_plan.end()

        await self.emit(
            {
                "type": "task_list",
                "tasks": [{"id": t.id, "title": t.title, "status": t.status} for t in self._state.work_plan.tasks],
            }
        )

        # Execute
        span_exec = langfuse_client.span(
            trace_id=self._trace_id,
            name="execute-plan",
            metadata={
                "total_tasks": len(self._state.work_plan.tasks),
                "execution_layers": len(self._state.work_plan.execution_layers()),
            },
        )
        self._observation_id = span_exec.id
        await self.emit({"type": "phase", "phase": "executing"})
        await self._execute()
        span_exec.end()

        # Summary
        span_summary = langfuse_client.span(trace_id=self._trace_id, name="generate-summary")
        self._observation_id = span_summary.id
        await self._generate_summary()
        span_summary.end()
        self._observation_id = None

        self._state.phase = "idle"
        self._state.work_plan = None
        await self.emit({"type": "phase", "phase": "complete"})
        await self.emit({"type": "action_complete"})

    # -- Planning --

    @observe(name="build-technical-plan")  # type: ignore[untyped-decorator]
    async def _build_technical_plan(self) -> WorkPlan:
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

        raw = await complete_chat(
            [Message.user(json.dumps(merge_data, indent=2))],
            render_merge(has_data_sources=bool(self._state.data_source_contexts)),
            model=self.model,
            metadata=self._llm_metadata("build_technical_plan"),
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
            architecture=self._state.architecture,
            ux_design=self._state.ux_design,
            tasks=tasks,
        )

    # -- Execution --

    async def _execute(self) -> None:
        if self._state.work_plan is None:
            raise RuntimeError("No work plan available")

        self._state.completed_files = {}
        self._state.task_files = {}

        langfuse_client = Langfuse()
        for layer in self._state.work_plan.execution_layers():
            await asyncio.gather(*[self._execute_task_with_span(t, langfuse_client) for t in layer])

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
            await self._fix_errors("\n\n".join(all_errors))

    async def _execute_task_with_span(self, task: Task, langfuse_client: Langfuse) -> None:
        span = langfuse_client.span(
            trace_id=self._trace_id,
            parent_observation_id=self._observation_id,
            name=f"execute-task-{task.id}",
            metadata={"task_id": task.id, "task_title": task.title, "expected_files": len(task.files)},
        )
        saved = self._observation_id
        self._observation_id = span.id
        try:
            await self._execute_task(task)
        finally:
            self._observation_id = saved
            span.end()

    async def _execute_task(self, task: Task) -> None:
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
            async for chunk in stream_chat(
                [Message.user("Generate the code.")],
                prompt,
                model=self.model,
                metadata=self._llm_metadata(f"execute_task_{task.id}"),
            ):
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
    async def _fix_errors(self, errors: str) -> None:
        await self.emit({"type": "phase", "phase": "fixing"})
        prompt = render_fix_errors(errors=errors, files=self._state.completed_files)
        try:
            generated: list[tuple[str, str]] = []
            parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))
            async for chunk in stream_chat(
                [Message.user("Fix the TypeScript errors.")],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("fix_errors"),
            ):
                parser.feed(chunk)
            parser.flush()

            for path, content in generated:
                await self.sandbox.write_file(path, content)
                self._state.completed_files[path] = content
                await self.emit({"type": "file", "path": path, "content": content})
        except Exception:
            logger.exception("[execute] Error fix pass failed")

    # -- Summary --

    async def _generate_summary(self) -> None:
        try:
            summary_input = json.dumps(
                {
                    "user_request": self._state.user_content,
                    "architecture": self._state.architecture.model_dump(),
                    "files_created": list(self._state.completed_files.keys()),
                },
                indent=2,
            )
            raw = await complete_chat(
                [Message.user(summary_input)],
                SUMMARY_PROMPT,
                model=self.model,
                metadata=self._llm_metadata("generate_summary"),
            )
            summary_data = parse_json_response(raw)
            if summary_data:
                await update_project_summary(self.project_id, json.dumps(summary_data, ensure_ascii=False))
                await self.emit({"type": "project_summary", "summary": summary_data})
        except Exception:
            logger.exception("[execute] Summary generation failed")
