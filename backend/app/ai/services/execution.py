from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

from app.ai.core.messages import Message
from app.ai.parser import ActionParser
from app.ai.provider import stream_chat
from app.ai.prompts import render_codegen, render_fix_errors
from app.ai.state import BuildState
from app.ai.task_tree import Task
from app.sandbox.filesystem import write_file
from app.sandbox.manager import sandbox_manager

logger = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        ws_send: Callable[[dict], Awaitable[None]],
        llm_metadata: Callable[[str], dict],
        trace_id: str | None = None,
    ) -> None:
        self.ws_send = ws_send
        self._llm_metadata = llm_metadata
        self._trace_id = trace_id
        self._observation_id: str | None = None

    async def execute(self, state: BuildState) -> BuildState:
        if state.work_plan is None:
            raise RuntimeError("No work plan available")

        state.completed_files = {}
        state.task_files = {}
        layers = state.work_plan.execution_layers()

        langfuse_client = Langfuse()
        for layer in layers:
            await asyncio.gather(
                *[self._execute_task_with_span(task, state, langfuse_client) for task in layer]
            )

        # Validate
        typecheck_errors, build_errors = await asyncio.gather(
            self._typecheck(state.session_id),
            self._build(state.session_id),
        )

        all_errors = []
        if typecheck_errors:
            all_errors.append("## TypeScript Errors\n" + typecheck_errors)
        if build_errors:
            all_errors.append("## Build Errors\n" + build_errors)

        if all_errors:
            combined = "\n\n".join(all_errors)
            await self._fix_errors(state, combined)

        return state

    async def _execute_task_with_span(self, task: Task, state: BuildState, langfuse_client: Langfuse) -> None:
        task_span = langfuse_client.span(
            trace_id=self._trace_id,
            parent_observation_id=self._observation_id,
            name=f"execute-task-{task.id}",
            metadata={
                "task_id": task.id,
                "task_title": task.title,
                "expected_files": len(task.files),
            },
        )
        saved_obs = self._observation_id
        self._observation_id = task_span.id
        try:
            await self._execute_task(task, state)
        finally:
            self._observation_id = saved_obs
            task_span.end()

    async def _execute_task(self, task: Task, state: BuildState) -> None:
        if state.work_plan is None:
            raise RuntimeError("No work plan available")

        task.status = "running"
        await self.ws_send({"type": "task_update", "taskId": task.id, "status": "running"})

        dep_file_paths: set[str] = set()
        for dep_id in task.depends_on:
            dep_file_paths.update(state.task_files.get(dep_id, []))

        dependency_files = {p: c for p, c in state.completed_files.items() if p in dep_file_paths}
        other_files = {p: c for p, c in state.completed_files.items() if p not in dep_file_paths}

        prompt = render_codegen(
            task_title=task.title,
            task_description=task.description,
            task_files=task.files,
            architecture=state.work_plan.architecture,
            ux_design=state.work_plan.ux_design,
            dependency_files=dependency_files or None,
            other_completed_files=other_files or None,
            case_contexts=state.case_contexts or None,
        )

        try:
            generated_files: list[tuple[str, str]] = []
            parser = ActionParser(
                on_file_action=lambda p, c: generated_files.append((p, c)),
            )

            async for chunk in stream_chat(
                [Message.user("Generate the code.")],
                prompt,
                model=state.model,
                metadata=self._llm_metadata(f"execute_task_{task.id}"),
            ):
                parser.feed(chunk)

            parser.flush()

            task_file_paths: list[str] = []
            for path, content in generated_files:
                await write_file(state.session_id, path, content)
                state.completed_files[path] = content
                task_file_paths.append(path)
                await self.ws_send({"type": "task_update", "taskId": task.id, "status": "running", "file": path})
                await self.ws_send({"type": "file", "path": path, "content": content})

            state.task_files[task.id] = task_file_paths
            task.status = "completed"
            await self.ws_send({"type": "task_update", "taskId": task.id, "status": "completed"})

        except Exception as exc:
            logger.exception("[execution] Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
            await self.ws_send({"type": "task_update", "taskId": task.id, "status": "failed"})

    async def _typecheck(self, session_id: str) -> str:
        try:
            lines: list[str] = []
            async for line in sandbox_manager.get_sandbox(session_id).exec("npx tsc --noEmit 2>&1"):
                lines.append(line.rstrip())
            return "\n".join(lines).strip()
        except Exception:
            logger.exception("[execution] Typecheck failed")
            return ""

    async def _build(self, session_id: str) -> str:
        try:
            lines: list[str] = []
            async for line in sandbox_manager.get_sandbox(session_id).exec("pnpm build 2>&1"):
                lines.append(line.rstrip())
            output = "\n".join(lines).strip()
            has_errors = output and ("error" in output.lower() or "failed" in output.lower())
            return output if has_errors else ""
        except Exception:
            logger.exception("[execution] Build failed")
            return ""

    @observe(name="fix-errors-auto")
    async def _fix_errors(self, state: BuildState, errors: str) -> None:
        await self.ws_send({"type": "phase", "phase": "fixing"})

        prompt = render_fix_errors(errors=errors, files=state.completed_files)

        try:
            generated_files: list[tuple[str, str]] = []
            parser = ActionParser(
                on_file_action=lambda p, c: generated_files.append((p, c)),
            )

            async for chunk in stream_chat(
                [Message.user("Fix the TypeScript errors.")],
                prompt,
                model=state.model,
                metadata=self._llm_metadata("fix_errors"),
            ):
                parser.feed(chunk)

            parser.flush()

            for path, content in generated_files:
                await write_file(state.session_id, path, content)
                state.completed_files[path] = content
                await self.ws_send({"type": "file", "path": path, "content": content})

            if generated_files:
                logger.info("[execution] Fixed %d files", len(generated_files))
        except Exception:
            logger.exception("[execution] Error fix pass failed")
