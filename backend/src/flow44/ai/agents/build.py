from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe

from flow44.ai.core.messages import Message
from flow44.ai.helpers import parse_json_response
from flow44.ai.parser import ActionParser
from flow44.ai.prompts import (
    SUMMARY_PROMPT,
    USER_PLAN_PROMPT,
    UX_DESIGN_PROMPT,
    render_architecture,
    render_codegen,
    render_fix_errors,
    render_merge,
    render_user_plan,
)
from flow44.ai.provider import complete_chat, stream_chat
from flow44.ai.schemas import ArchitectureDesign, UserPlanOverview, UXDesign
from flow44.ai.state import BuildState
from flow44.ai.task_tree import Task, WorkPlan
from flow44.integrations.package_api import PackageApiUpstreamError
from flow44.integrations.package_cases import fetch_case_package_data
from flow44.models.project import update_project_summary
from flow44.sandbox.filesystem import write_file
from flow44.sandbox.manager import sandbox_manager

from ._base import BaseAgent

logger = logging.getLogger(__name__)


# TODO: maybe split this into two agents and get rid of the approval event stuff?
# TODO: or think about how to add support for it in the Flow framework.
class BuildAgent(BaseAgent):
    def __init__(
        self,
        *,
        package_api_authorization: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._state = BuildState(session_id=self.session_id, project_id=self.project_id, model=self.model)
        self._observation_id: str | None = None
        self._approval_event = asyncio.Event()
        self._approval_action: str = "reject"
        self._approval_feedback: str | None = None
        self._package_api_authorization = package_api_authorization

    @observe(name="build-agent-run")  # type: ignore[untyped-decorator]
    async def run(self, content: str, case_ids: list[str] | None = None) -> None:
        self._state.user_content = content
        self._state.case_ids = case_ids or []
        self._trace_id = langfuse_context.get_current_trace_id()

        langfuse_context.update_current_trace(
            session_id=self.session_id,
            user_id=self.project_id,
            metadata={"model": self.model or "default"},
            tags=["build-agent"],
        )

        # Fetch case data
        if self._state.case_ids:
            await self.emit({"type": "phase", "phase": "fetching_cases"})
            results = await asyncio.gather(
                *[self._fetch_and_analyze_case(cid) for cid in self._state.case_ids],
                return_exceptions=True,
            )
            failures = [r for r in results if isinstance(r, Exception)]
            if failures:
                await self.emit(
                    {
                        "type": "error",
                        "message": "Build aborted: failed to fetch required case data.",
                    }
                )
                await self.emit({"type": "phase", "phase": "idle"})
                return
            self._state.case_contexts = [ctx for ctx in results if ctx is not None and not isinstance(ctx, Exception)]

            if self._state.case_contexts:
                from flow44.models.project import update_project_cases  # noqa: PLC0415

                await update_project_cases(self.project_id, self._state.case_contexts)

                await self.emit(
                    {
                        "type": "cases_fetched",
                        "cases": [
                            {
                                "package_id": ctx["package_id"],
                                "package_name": ctx["package_name"],
                                "data_schema": ctx.get("data_schema", ""),
                                "relevant_fields": ctx.get("relevant_fields", ""),
                            }
                            for ctx in self._state.case_contexts
                        ],
                    }
                )

        # Design (parallel)
        await self.emit({"type": "phase", "phase": "designing"})
        self._state.architecture, self._state.ux_design = await asyncio.gather(
            self._design_architecture(),
            self._design_ux(),
        )

        # Build user overview
        await self.emit({"type": "phase", "phase": "planning"})
        self._state.user_overview = await self._build_user_overview()

        # Present for approval and wait
        self._state.phase = "awaiting_approval"
        await self.emit({"type": "phase", "phase": "awaiting_approval"})
        await self.emit({"type": "plan_overview", "overview": self._state.user_overview.model_dump()})

        # Approval loop: wait for user response, handle modify/reject/accept
        while True:
            self._approval_event.clear()
            await self._approval_event.wait()

            if self._approval_action == "accept":
                break
            elif self._approval_action == "modify" and self._approval_feedback:
                await self.emit({"type": "phase", "phase": "planning"})
                self._state.user_overview = await self._rebuild_overview_with_feedback(self._approval_feedback)
                self._state.phase = "awaiting_approval"
                await self.emit({"type": "phase", "phase": "awaiting_approval"})
                await self.emit({"type": "plan_overview", "overview": self._state.user_overview.model_dump()})
            elif self._approval_action == "reject":
                await self.emit({"type": "plan_rejected", "overview": self._state.user_overview.model_dump()})
                self._state = BuildState(session_id=self.session_id, project_id=self.project_id, model=self.model)
                await self.emit({"type": "phase", "phase": "idle"})
                return

        await self._accept_plan()

    def signal_plan_response(self, action: str, feedback: str | None = None) -> None:
        self._approval_action = action
        self._approval_feedback = feedback
        self._approval_event.set()

    async def _accept_plan(self) -> None:
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

    # -- Design --

    async def _fetch_and_analyze_case(self, package_id: str) -> dict[str, Any] | None:
        try:
            package_name, sample_data = await fetch_case_package_data(
                package_id,
                authorization=self._package_api_authorization,
            )

            analysis_prompt = (
                f"Analyze this API package data in the context of the user's request.\n\n"
                f"User wants to build: {self._state.user_content}\n\n"
                f"Package: {package_name}\nSample API Response:\n```json\n"
                f"{json.dumps(sample_data, indent=2)[:2000]}\n```\n\n"
                f'Respond with ONLY a JSON object:\n{{"data_schema": "...", "relevant_fields": "...", '
                f'"data_characteristics": "...", "integration_notes": "..."}}'
            )

            try:
                raw = await complete_chat(
                    [Message.user(analysis_prompt)],
                    "You are a software architect analyzing API data for integration.",
                    model=self.model,
                    metadata=self._llm_metadata("package_analysis"),
                )
                analysis = parse_json_response(raw)
            except Exception:
                logger.exception("[build] Package analysis failed")
                analysis = {
                    "data_schema": (
                        f"Package data with "
                        f"{len(sample_data) if isinstance(sample_data, list) else 'structured'} records"
                    ),
                    "relevant_fields": "See raw data",
                    "data_characteristics": "Fetched from API",
                    "integration_notes": f"Data preview: {json.dumps(sample_data, indent=2)[:500]}",
                }

            return {"package_id": package_id, "package_name": package_name, "sample_data": sample_data, **analysis}

        except LookupError as e:
            await self.emit({"type": "case_error", "message": f"Package {package_id} not found"})
            raise RuntimeError(f"Case fetch failed for package {package_id}: not found") from e
        except PackageApiUpstreamError as e:
            await self.emit({"type": "case_error", "message": f"Failed to fetch package data: {e}"})
            raise RuntimeError(f"Case fetch failed for package {package_id}: upstream error") from e
        except Exception as e:
            logger.exception("[build] Unexpected error fetching package")
            await self.emit({"type": "case_error", "message": "Unexpected error fetching package data"})
            raise RuntimeError(f"Case fetch failed for package {package_id}: unexpected error") from e

    @observe(name="design-architecture")  # type: ignore[untyped-decorator]
    async def _design_architecture(self) -> ArchitectureDesign:
        prompt = render_architecture(case_contexts=self._state.case_contexts or None)
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
            logger.exception("[build] Architecture design failed")
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
            logger.exception("[build] UX design failed")
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
            USER_PLAN_PROMPT,
            model=self.model,
            metadata=self._llm_metadata("build_user_overview"),
        )
        return UserPlanOverview.model_validate(parse_json_response(raw))

    async def _rebuild_overview_with_feedback(self, feedback: str) -> UserPlanOverview:
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
            metadata=self._llm_metadata("rebuild_overview_with_feedback"),
        )
        return UserPlanOverview.model_validate(parse_json_response(raw))

    # -- Planning --

    @observe(name="build-technical-plan")  # type: ignore[untyped-decorator]
    async def _build_technical_plan(self) -> WorkPlan:
        merge_data: dict[str, object] = {
            "user_request": self._state.user_content,
            "architecture": self._state.architecture.model_dump(),
            "ux_design": self._state.ux_design.model_dump(),
            "user_preferences": [d.model_dump() for d in self._state.user_overview.decisions],
        }
        if self._state.case_contexts:
            merge_data["case_integrations"] = [
                {
                    k: ctx[k]
                    for k in (
                        "package_id",
                        "package_name",
                        "data_schema",
                        "relevant_fields",
                        "data_characteristics",
                        "integration_notes",
                    )
                }
                for ctx in self._state.case_contexts
            ]

        raw = await complete_chat(
            [Message.user(json.dumps(merge_data, indent=2))],
            render_merge(has_cases=bool(self._state.case_contexts)),
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
            case_contexts=self._state.case_contexts or None,
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
                await write_file(self.session_id, path, content)
                self._state.completed_files[path] = content
                paths.append(path)
                await self.emit({"type": "task_update", "taskId": task.id, "status": "running", "file": path})
                await self.emit({"type": "file", "path": path, "content": content})

            self._state.task_files[task.id] = paths
            task.status = "completed"
            await self.emit({"type": "task_update", "taskId": task.id, "status": "completed"})
        except Exception as exc:
            logger.exception("[build] Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
            await self.emit({"type": "task_update", "taskId": task.id, "status": "failed"})

    async def _typecheck(self) -> str:
        try:
            sandbox = sandbox_manager.get_sandbox(self.session_id)
            if sandbox is None:
                return ""
            lines: list[str] = []
            async for line in sandbox.exec("npx tsc --noEmit 2>&1"):
                lines.append(line.rstrip())
            return "\n".join(lines).strip()
        except Exception:
            logger.exception("[build] Typecheck failed")
            return ""

    async def _build(self) -> str:
        try:
            sandbox = sandbox_manager.get_sandbox(self.session_id)
            if sandbox is None:
                return ""
            lines: list[str] = []
            async for line in sandbox.exec("pnpm build 2>&1"):
                lines.append(line.rstrip())
            output = "\n".join(lines).strip()
            return output if output and ("error" in output.lower() or "failed" in output.lower()) else ""
        except Exception:
            logger.exception("[build] Build failed")
            return ""

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
                await write_file(self.session_id, path, content)
                self._state.completed_files[path] = content
                await self.emit({"type": "file", "path": path, "content": content})
        except Exception:
            logger.exception("[build] Error fix pass failed")

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
            logger.exception("[build] Summary generation failed")
