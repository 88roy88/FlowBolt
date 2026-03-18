"""Multi-phase agent orchestrator.

Routes user messages through: classify → design → user overview → approve → technical plan → execute.
Follow-up edits bypass the agent and use the existing single-turn flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Awaitable

from app.config import settings
from app.integrations.package_api import PackageApiClient, PackageApiUpstreamError
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context
from app.ai.parser import ActionParser
from app.ai.provider import complete_chat, stream_chat
from app.sandbox.nsjail import exec_in_sandbox
from app.ai.task_tree import Task, WorkPlan
from app.ai.prompts import (
    CLASSIFY_PROMPT,
    ARCHITECTURE_PROMPT,
    UX_DESIGN_PROMPT,
    USER_PLAN_PROMPT,
    MERGE_PROMPT,
    SUMMARY_PROMPT,
    get_codegen_prompt,
)
from app.ai.prompts_legacy import get_system_prompt
from app.models.chat import get_messages, save_message
from app.models.project import get_project_by_session, update_project_summary
from app.sandbox.filesystem import write_file, read_file, list_files

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Manages the multi-phase agent flow for a single session."""

    def __init__(
        self,
        session_id: str,
        project_id: str,
        ws_send: Callable[[dict], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self.ws_send = ws_send
        self.state = "idle"
        self.model: str | None = None
        self._user_content: str = ""
        self._package_id: str | None = None
        self._package_results: dict | None = None
        # Internal design artifacts (never shown raw to the user)
        self._architecture: dict = {}
        self._ux_design: dict = {}
        # User-facing overview (shown for approval)
        self._user_overview: dict = {}
        # Technical plan (built after approval, used for execution)
        self._work_plan: WorkPlan | None = None
        self._completed_files: dict[str, str] = {}
        # Track which files belong to which task for dependency context
        self._task_files: dict[str, list[str]] = {}  # task_id -> [file_paths]
        # Store trace_id and observation_id to maintain single trace across multiple method calls
        self._trace_id: str | None = None
        self._observation_id: str | None = None

    def _llm_metadata(self, generation_name: str) -> dict:
        """Build metadata for LiteLLM calls with trace context."""
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        observation_id = self._observation_id or langfuse_context.get_current_observation_id()

        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }

    @observe(name="agent-handle-message", as_type="span")
    async def handle_message(
        self,
        content: str,
        model: str | None = None,
        package_id: str | None = None,
    ) -> None:
        """Process a new user message through the agent pipeline."""
        self.model = model
        self._user_content = content
        self._package_id = package_id
        self._package_results = None

        # 0. If user selected a package, run it first and store the results.
        if package_id:
            try:
                self._package_results = await self._run_selected_package(package_id)
            except Exception as exc:
                logger.exception("[agent] Package run failed (package_id=%s)", package_id)
                await self.ws_send({"type": "error", "message": f"Package run failed for id={package_id}"})
                raise exc

        # Capture trace_id to maintain single trace across method calls
        self._trace_id = langfuse_context.get_current_trace_id()

        # Add trace-level metadata
        langfuse_context.update_current_trace(
            session_id=self.session_id,
            user_id=self.project_id,
            metadata={
                "model": model or "default",
                "project_id": self.project_id,
            },
            tags=["agent-flow", "new-message"],
        )

        # 1. Classify
        await self.ws_send({"type": "phase", "phase": "classifying"})
        is_new = await self._classify(content)

        if not is_new:
            await self._simple_flow(content)
            return

        # 2. Design (parallel, internal)
        await self.ws_send({"type": "phase", "phase": "designing"})
        self._architecture, self._ux_design = await asyncio.gather(
            self._design_architecture(content),
            self._design_ux(content),
        )

        # Save design complete card
        await save_message(self.project_id, "assistant", encode_card({
            "type": "design_complete",
            "architecture": bool(self._architecture),
            "ux": bool(self._ux_design),
        }))

        # 3. Build user-friendly overview from the designs
        await self.ws_send({"type": "phase", "phase": "planning"})
        self._user_overview = await self._build_user_overview(content)

        # 4. Present overview to user for approval
        self.state = "awaiting_approval"
        await self.ws_send({"type": "phase", "phase": "awaiting_approval"})
        await self.ws_send({
            "type": "plan_overview",
            "overview": self._user_overview,
        })

    async def handle_plan_response(
        self,
        action: str,
        feedback: str | None = None,
    ) -> None:
        """Handle user's response to the overview."""
        if action == "accept":
            # Save accepted plan card
            await save_message(self.project_id, "assistant", encode_card({
                "type": "plan_overview",
                "overview": self._user_overview,
                "accepted": True,
            }))

            # Use stored trace_id to continue the same trace
            if self._trace_id:
                langfuse_client = Langfuse()

                # Build the technical plan internally
                await self.ws_send({"type": "phase", "phase": "planning"})
                span_plan = langfuse_client.span(
                    trace_id=self._trace_id,
                    name="build-technical-plan",
                )
                # Store observation ID for LLM calls within this span
                self._observation_id = span_plan.id
                self._work_plan = await self._build_technical_plan()
                span_plan.end()

                # Send task list for progress UI (titles only, no file paths)
                await self.ws_send({
                    "type": "task_list",
                    "tasks": [
                        {"id": t.id, "title": t.title, "status": t.status}
                        for t in self._work_plan.tasks
                    ],
                })

                # Execute
                span_execute = langfuse_client.span(
                    trace_id=self._trace_id,
                    name="execute-plan",
                    metadata={
                        "total_tasks": len(self._work_plan.tasks),
                        "execution_layers": len(self._work_plan.execution_layers()),
                    }
                )
                # Store observation ID for LLM calls within this span
                self._observation_id = span_execute.id
                await self._execute()
                span_execute.end()

                # Reset observation_id after execution
                self._observation_id = None

                # Generate summary as a sibling span (top-level under trace)
                span_summary = langfuse_client.span(
                    trace_id=self._trace_id,
                    name="generate-summary",
                )
                # Store observation ID for LLM calls within this span
                self._observation_id = span_summary.id
                await self._generate_summary()
                span_summary.end()

                # Reset observation_id after summary
                self._observation_id = None
            else:
                # Fallback if no trace_id (shouldn't happen)
                await self.ws_send({"type": "phase", "phase": "planning"})
                self._work_plan = await self._build_technical_plan()
                await self.ws_send({
                    "type": "task_list",
                    "tasks": [
                        {"id": t.id, "title": t.title, "status": t.status}
                        for t in self._work_plan.tasks
                    ],
                })
                await self._execute()

        elif action == "modify":
            if feedback:
                await self.ws_send({"type": "phase", "phase": "planning"})
                self._user_overview = await self._rebuild_overview_with_feedback(feedback)
                self.state = "awaiting_approval"
                await self.ws_send({"type": "phase", "phase": "awaiting_approval"})
                await self.ws_send({
                    "type": "plan_overview",
                    "overview": self._user_overview,
                })

        elif action == "reject":
            self.state = "idle"
            self._architecture = {}
            self._ux_design = {}
            self._user_overview = {}
            self._work_plan = None
            await self.ws_send({"type": "phase", "phase": "idle"})

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @observe(name="classify-request", as_type="span")
    async def _classify(self, content: str) -> bool:
        """Return True if this is a new project request, False for follow-up."""
        history = await get_messages(self.project_id)
        # Only count real assistant messages, not card metadata
        assistant_msgs = [
            m for m in history
            if m.role == "assistant" and not m.content.startswith(CARD_PREFIX)
        ]
        if len(assistant_msgs) == 0:
            logger.info("[agent] First message — classifying as new_project")
            langfuse_context.update_current_observation(
                metadata={"classification": "new_project", "reason": "first_message"}
            )
            return True

        # Include project summary for classifier context
        classify_content = content
        project = await get_project_by_session(self.session_id)
        if project and project.summary:
            try:
                summary_data = json.loads(project.summary)
                classify_content = (
                    f"[Existing project: {summary_data.get('summary', '')}]\n\n"
                    f"User message: {content}"
                )
            except (json.JSONDecodeError, AttributeError):
                pass

        messages = [{"role": "user", "content": classify_content}]
        try:
            raw = await complete_chat(
                messages,
                CLASSIFY_PROMPT,
                model=self.model,
                metadata=self._llm_metadata("classify")
            )
            data = json.loads(raw.strip())
            classification = data.get("classification", "follow_up")
            logger.info("[agent] Classification: %s", classification)
            is_new = classification == "new_project"
            langfuse_context.update_current_observation(
                metadata={"classification": classification, "is_new_project": is_new}
            )
            return is_new
        except Exception:
            logger.exception("[agent] Classification failed, defaulting to follow_up")
            langfuse_context.update_current_observation(
                metadata={"classification": "follow_up", "reason": "error_fallback"}
            )
            return False

    # ------------------------------------------------------------------
    # Design phase (internal)
    # ------------------------------------------------------------------

    @observe(name="design-architecture", as_type="span")
    async def _design_architecture(self, content: str) -> dict:
        messages = [{"role": "user", "content": content}]
        try:
            raw = await complete_chat(
                messages,
                ARCHITECTURE_PROMPT,
                model=self.model,
                metadata=self._llm_metadata("design_architecture")
            )
            await self.ws_send({"type": "design_progress", "stream": "architecture", "content": "complete"})
            result = _parse_json_response(raw)
            langfuse_context.update_current_observation(
                metadata={"success": True, "components_count": len(result.get("components", []))}
            )
            return result
        except Exception:
            logger.exception("[agent] Architecture design failed")
            await self.ws_send({"type": "design_progress", "stream": "architecture", "content": "failed"})
            langfuse_context.update_current_observation(
                metadata={"success": False}
            )
            return {}

    @observe(name="design-ux", as_type="span")
    async def _design_ux(self, content: str) -> dict:
        messages = [{"role": "user", "content": content}]
        try:
            raw = await complete_chat(
                messages,
                UX_DESIGN_PROMPT,
                model=self.model,
                metadata=self._llm_metadata("design_ux")
            )
            await self.ws_send({"type": "design_progress", "stream": "ux", "content": "complete"})
            result = _parse_json_response(raw)
            langfuse_context.update_current_observation(
                metadata={"success": True, "screens_count": len(result.get("screens", []))}
            )
            return result
        except Exception:
            logger.exception("[agent] UX design failed")
            await self.ws_send({"type": "design_progress", "stream": "ux", "content": "failed"})
            langfuse_context.update_current_observation(
                metadata={"success": False}
            )
            return {}

    # ------------------------------------------------------------------
    # User-facing overview
    # ------------------------------------------------------------------

    @observe(name="build-user-overview", as_type="span")
    async def _build_user_overview(self, content: str) -> dict:
        """Build a friendly, non-technical overview for the user."""
        plan_input = json.dumps({
            "user_request": content,
            "package_id": self._package_id,
            "package_results": self._package_results,
            "architecture": self._architecture,
            "ux_design": self._ux_design,
        }, indent=2)
        messages = [{"role": "user", "content": plan_input}]
        raw = await complete_chat(
            messages,
            USER_PLAN_PROMPT,
            model=self.model,
            metadata=self._llm_metadata("build_user_overview")
        )
        result = _parse_json_response(raw)
        langfuse_context.update_current_observation(
            metadata={"decisions_count": len(result.get("decisions", []))}
        )
        return result

    async def _rebuild_overview_with_feedback(self, feedback: str) -> dict:
        """Re-generate the user overview incorporating user feedback.

        Also re-run the internal design calls so the architecture/UX
        designs reflect the feedback before we later build the technical plan.
        """
        plan_input = json.dumps({
            "user_request": self._user_content,
            "package_id": self._package_id,
            "package_results": self._package_results,
            "architecture": self._architecture,
            "ux_design": self._ux_design,
            "previous_overview": self._user_overview,
            "user_feedback": feedback,
        }, indent=2)
        messages = [{"role": "user", "content": plan_input}]
        raw = await complete_chat(
            messages,
            USER_PLAN_PROMPT + "\n\nThe user has reviewed a previous plan and provided feedback. "
            "Update the overview to reflect their preferences. If they chose an alternative "
            "for a decision, switch the 'chosen' field accordingly.",
            model=self.model,
            metadata=self._llm_metadata("rebuild_overview_with_feedback")
        )
        return _parse_json_response(raw)

    # ------------------------------------------------------------------
    # Technical plan (internal, built after user approval)
    # ------------------------------------------------------------------

    async def _build_technical_plan(self) -> WorkPlan:
        """Build the detailed technical task plan from designs + user decisions."""
        merge_input = json.dumps({
            "user_request": self._user_content,
            "package_id": self._package_id,
            "package_results": self._package_results,
            "architecture": self._architecture,
            "ux_design": self._ux_design,
            "user_preferences": self._user_overview.get("decisions", []),
        }, indent=2)
        messages = [{"role": "user", "content": merge_input}]
        raw = await complete_chat(
            messages,
            MERGE_PROMPT,
            model=self.model,
            metadata=self._llm_metadata("build_technical_plan")
        )
        plan_data = _parse_json_response(raw)
        work_plan = _dict_to_work_plan(plan_data, self._architecture, self._ux_design)
        langfuse_context.update_current_observation(
            metadata={"tasks_count": len(work_plan.tasks)}
        )
        return work_plan

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute(self) -> None:
        """Execute the technical plan layer by layer."""
        assert self._work_plan is not None
        self.state = "executing"
        await self.ws_send({"type": "phase", "phase": "executing"})

        self._completed_files = {}
        self._task_files = {}
        layers = self._work_plan.execution_layers()

        langfuse_client = Langfuse()
        for layer in layers:
            await asyncio.gather(
                *[self._execute_task_with_span(task, langfuse_client) for task in layer]
            )

        # Save task progress card
        await save_message(self.project_id, "assistant", encode_card({
            "type": "task_progress",
            "tasks": [
                {"id": t.id, "title": t.title, "status": t.status}
                for t in self._work_plan.tasks
            ],
        }))

        # Run both typecheck and build to catch errors
        typecheck_errors, build_errors = await asyncio.gather(
            self._typecheck(),
            self._build(),
        )

        # Combine all errors
        all_errors = []
        if typecheck_errors:
            all_errors.append("## TypeScript Errors\n" + typecheck_errors)
        if build_errors:
            all_errors.append("## Build Errors\n" + build_errors)

        if all_errors:
            combined_errors = "\n\n".join(all_errors)
            await self._fix_errors(combined_errors)

        self.state = "idle"
        self._work_plan = None
        await self.ws_send({"type": "phase", "phase": "complete"})
        await self.ws_send({"type": "action_complete"})

    async def _execute_task_with_span(self, task: Task, langfuse_client: Langfuse) -> None:
        """Wrapper to execute a task with its own span nested under execute-plan."""
        # Create a child span under the execute-plan span (self._observation_id)
        task_span = langfuse_client.span(
            trace_id=self._trace_id,
            parent_observation_id=self._observation_id,
            name=f"execute-task-{task.id}",
            metadata={
                "task_id": task.id,
                "task_title": task.title,
                "task_description": task.description,
                "dependencies": task.depends_on,
                "expected_files": len(task.files),
            },
        )

        # Temporarily save current observation_id and replace with task span
        parent_observation_id = self._observation_id
        self._observation_id = task_span.id

        try:
            await self._execute_task(task)
        finally:
            # Restore parent observation_id and end task span
            self._observation_id = parent_observation_id
            task_span.end()

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task: call AI for code, parse XML, write files."""
        task.status = "running"
        await self.ws_send({
            "type": "task_update",
            "taskId": task.id,
            "status": "running",
        })

        assert self._work_plan is not None

        # Split completed files into dependency (full) vs other (exports only)
        dep_file_paths: set[str] = set()
        for dep_id in task.depends_on:
            dep_file_paths.update(self._task_files.get(dep_id, []))

        dependency_files: dict[str, str] = {}
        other_completed_files: dict[str, str] = {}
        for path, content in self._completed_files.items():
            if path in dep_file_paths:
                dependency_files[path] = content
            else:
                other_completed_files[path] = content

        prompt = get_codegen_prompt(
            task_title=task.title,
            task_description=task.description,
            task_files=task.files,
            architecture=self._work_plan.architecture,
            ux_design=self._work_plan.ux_design,
            package_data=self._package_results,
            dependency_files=dependency_files or None,
            other_completed_files=other_completed_files or None,
        )

        try:
            generated_files: list[tuple[str, str]] = []
            parser = ActionParser(
                on_file_action=lambda p, c: generated_files.append((p, c)),
            )

            full_text: list[str] = []
            async for chunk in stream_chat(
                [{"role": "user", "content": "Generate the code."}],
                prompt,
                model=self.model,
                metadata=self._llm_metadata(f"execute_task_{task.id}")
            ):
                full_text.append(chunk)
                parser.feed(chunk)

            parser.flush()

            task_file_paths: list[str] = []
            for path, content in generated_files:
                await write_file(self.session_id, path, content)
                self._completed_files[path] = content
                task_file_paths.append(path)
                await self.ws_send({
                    "type": "task_update",
                    "taskId": task.id,
                    "status": "running",
                    "file": path,
                })
                await self.ws_send({"type": "file", "path": path, "content": content})

            self._task_files[task.id] = task_file_paths
            task.status = "completed"
            await self.ws_send({
                "type": "task_update",
                "taskId": task.id,
                "status": "completed",
            })

        except Exception as exc:
            logger.exception("[agent] Task %s failed", task.id)
            task.status = "failed"
            task.error = str(exc)
            await self.ws_send({
                "type": "task_update",
                "taskId": task.id,
                "status": "failed",
            })

    # ------------------------------------------------------------------
    # Typecheck and Build
    # ------------------------------------------------------------------

    async def _typecheck(self) -> str:
        """Run tsc --noEmit and return error output (empty string if clean)."""
        try:
            lines: list[str] = []
            async for line in exec_in_sandbox(
                self.session_id,
                "npx tsc --noEmit 2>&1",
            ):
                lines.append(line.rstrip())
            output = "\n".join(lines).strip()
            if output:
                logger.info("[agent] Typecheck found errors:\n%s", output)
            else:
                logger.info("[agent] Typecheck passed")
            return output
        except Exception:
            logger.exception("[agent] Typecheck execution failed")
            return ""

    @observe(name="build-validation", as_type="span")
    async def _build(self) -> str:
        """Run pnpm build and return error output (empty string if clean)."""
        langfuse_client = Langfuse()
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        parent_id = langfuse_context.get_current_observation_id()

        # Span for typecheck
        span_typecheck = langfuse_client.span(
            trace_id=trace_id,
            parent_observation_id=parent_id,
            name="typecheck",
            metadata={"command": "npx tsc --noEmit"}
        )

        typecheck_output = ""
        typecheck_success = False
        try:
            lines: list[str] = []
            async for line in exec_in_sandbox(
                self.session_id,
                "npx tsc --noEmit 2>&1",
            ):
                lines.append(line.rstrip())
            typecheck_output = "\n".join(lines).strip()
            typecheck_success = not bool(typecheck_output)

            span_typecheck.end(
                metadata={
                    "command": "npx tsc --noEmit",
                    "success": typecheck_success,
                    "has_errors": bool(typecheck_output),
                    "error_output": typecheck_output if typecheck_output else None,
                }
            )

            if typecheck_output:
                logger.info("[agent] Typecheck found errors:\n%s", typecheck_output)
            else:
                logger.info("[agent] Typecheck passed")
        except Exception as exc:
            logger.exception("[agent] Typecheck execution failed")
            span_typecheck.end(
                metadata={
                    "command": "npx tsc --noEmit",
                    "success": False,
                    "exception": str(exc),
                }
            )

        # Span for build
        span_build = langfuse_client.span(
            trace_id=trace_id,
            parent_observation_id=parent_id,
            name="build",
            metadata={"command": "pnpm build"}
        )

        build_output = ""
        build_success = False
        try:
            lines: list[str] = []
            async for line in exec_in_sandbox(
                self.session_id,
                "pnpm build 2>&1",
            ):
                lines.append(line.rstrip())
            build_output = "\n".join(lines).strip()
            has_errors = build_output and ("error" in build_output.lower() or "failed" in build_output.lower())
            build_success = not has_errors

            span_build.end(
                metadata={
                    "command": "pnpm build",
                    "success": build_success,
                    "has_errors": has_errors,
                    "error_output": build_output if has_errors else None,
                }
            )

            if has_errors:
                logger.info("[agent] Build found errors:\n%s", build_output)
                return build_output
            else:
                logger.info("[agent] Build passed")
                return ""
        except Exception as exc:
            logger.exception("[agent] Build execution failed")
            span_build.end(
                metadata={
                    "command": "pnpm build",
                    "success": False,
                    "exception": str(exc),
                }
            )
            return ""

    @observe(name="fix-errors-auto", as_type="span")
    async def _fix_errors(self, errors: str) -> None:
        """Ask the LLM to fix typecheck errors, then write the corrected files."""
        assert self._work_plan is not None
        await self.ws_send({"type": "phase", "phase": "fixing"})

        # Add metadata about the errors being fixed
        error_lines = errors.strip().split("\n")
        langfuse_context.update_current_observation(
            metadata={
                "error_count": len(error_lines),
                "error_preview": errors[:500],  # First 500 chars
                "files_in_context": len(self._completed_files),
            }
        )

        prompt = f"""\
You are an expert React/TypeScript developer. The project was just built but has
errors. Fix ALL errors below by outputting corrected files.

## Errors
```
{errors}
```

## Current Files
"""
        for path, content in self._completed_files.items():
            prompt += f"\n### {path}\n```\n{content}\n```\n"

        prompt += """
## Output Format
Respond using the boltArtifact XML format. Only output files that need changes.

```xml
<boltArtifact id="fix-errors" title="Fix TypeScript errors">
  <boltAction type="file" filePath="path/to/file.tsx">
    Full corrected file content
  </boltAction>
</boltArtifact>
```

Rules:
1. Fix ALL reported errors.
2. Do NOT change functionality — only fix type errors.
3. Output complete file contents, not patches.
4. Do NOT include shell actions.
"""
        try:
            generated_files: list[tuple[str, str]] = []
            parser = ActionParser(
                on_file_action=lambda p, c: generated_files.append((p, c)),
            )

            full_text: list[str] = []
            async for chunk in stream_chat(
                [{"role": "user", "content": "Fix the TypeScript errors."}],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("fix_errors")
            ):
                full_text.append(chunk)
                parser.feed(chunk)

            parser.flush()

            # Write fixed files
            for path, content in generated_files:
                await write_file(self.session_id, path, content)
                self._completed_files[path] = content
                await self.ws_send({"type": "file", "path": path, "content": content})

            if generated_files:
                logger.info("[agent] Fixed %d files after typecheck", len(generated_files))
                # Update observation with results
                langfuse_context.update_current_observation(
                    metadata={
                        "files_fixed": len(generated_files),
                        "fixed_file_paths": [p for p, _ in generated_files],
                        "success": True,
                    }
                )
        except Exception as exc:
            logger.exception("[agent] Error fix pass failed")
            langfuse_context.update_current_observation(
                metadata={
                    "success": False,
                    "exception": str(exc),
                }
            )

    # ------------------------------------------------------------------
    # Direct error fixing (for "Fix with AI" button)
    # ------------------------------------------------------------------

    @observe(name="fix-error-direct", as_type="span")
    async def handle_fix_error(
        self,
        error_message: str,
        error_file: str | None = None,
        error_line: int | None = None,
        error_stack: str | None = None,
        model: str | None = None,
    ) -> None:
        """Fix a build/runtime error directly without full agent flow.

        This is used by the "Fix with AI" button in the error toast.
        """
        self.model = model
        self._trace_id = langfuse_context.get_current_trace_id()

        # Add metadata about the error to the parent span
        langfuse_context.update_current_observation(
            metadata={
                "error_message": error_message[:200],  # Truncate for readability
                "error_file": error_file,
                "error_line": error_line,
                "has_stack": bool(error_stack),
                "model": self.model,
            }
        )

        await self.ws_send({"type": "phase", "phase": "fixing"})

        # Track steps for persisting to chat history
        fix_steps: list[dict] = []
        explanation_text = ""

        # Send initial step
        await self.ws_send({
            "type": "fix_step",
            "step": "discover",
            "status": "running",
            "message": "Discovering files to fix..."
        })
        fix_steps.append({
            "id": str(uuid.uuid4()),
            "step": "discover",
            "status": "running",
            "message": "Discovering files to fix..."
        })

        # Determine which file(s) to fix - wrap in a span
        langfuse_client = Langfuse()
        span_discovery = langfuse_client.span(
            trace_id=self._trace_id,
            parent_observation_id=langfuse_context.get_current_observation_id(),
            name="discover-files-to-fix",
            metadata={
                "error_file": error_file,
                "error_line": error_line,
            },
        )

        files_to_read: list[str] = []
        if error_file:
            # Normalize the file path to be relative to workspace (e.g., /src/App.tsx)
            file_path = error_file

            # If it's an absolute path with workspace directory, extract the relative part
            if f"/{self.session_id}/" in file_path:
                # Extract everything after the session_id
                idx = file_path.find(f"/{self.session_id}/")
                if idx != -1:
                    file_path = file_path[idx + len(self.session_id) + 2:]  # +2 for the two slashes
                    if not file_path.startswith("/"):
                        file_path = "/" + file_path
            # If it already starts with /src/, it's correct
            elif not file_path.startswith("/src/"):
                # Try to extract just the /src/... part
                # Look for /src/ but make sure it's the actual src directory
                if "/src/" in file_path:
                    # Find the last occurrence of /src/ (most likely to be the project src)
                    src_idx = file_path.rfind("/src/")
                    file_path = file_path[src_idx:]
                elif not file_path.startswith("/"):
                    file_path = "/src/" + file_path
                else:
                    file_path = "/src" + file_path

            files_to_read.append(file_path)
        else:
            # No specific file, try to read all source files
            try:
                tree = await list_files(self.session_id)
                for entry in tree:
                    if entry.name == "src" and entry.children:
                        for child in entry.children:
                            if child.path.endswith((".tsx", ".ts", ".jsx", ".js")):
                                files_to_read.append(child.path)
            except Exception:
                logger.warning("[agent] Could not read file tree for error fix")

        # Read the files
        file_contents: dict[str, str] = {}
        files_read_successfully: list[str] = []
        files_read_failed: list[str] = []

        for path in files_to_read[:10]:  # Limit to 10 files to avoid token overflow
            try:
                content = await read_file(self.session_id, path)
                file_contents[path] = content
                files_read_successfully.append(path)
            except Exception as e:
                logger.warning("[agent] Could not read file %s for error fix: %s", path, str(e))
                files_read_failed.append(path)

                # If specific file doesn't exist, try to find relevant files
                if not file_contents and error_file:
                    # File might not exist yet or path is wrong, read all src files instead
                    logger.info("[agent] Attempting to read all source files as fallback")
                    try:
                        tree = await list_files(self.session_id)
                        for entry in tree:
                            if entry.name == "src" and entry.children:
                                for child in entry.children:
                                    if child.path.endswith((".tsx", ".ts", ".jsx", ".js", ".css")):
                                        try:
                                            content = await read_file(self.session_id, child.path)
                                            file_contents[child.path] = content
                                            files_read_successfully.append(child.path)
                                        except Exception:
                                            pass
                                break
                    except Exception as fallback_err:
                        logger.warning("[agent] Fallback file reading failed: %s", str(fallback_err))

        # End discovery span with output metadata
        span_discovery.update(
            output={
                "files_discovered": len(files_to_read),
                "files_read_successfully": len(files_read_successfully),
                "files_read_failed": len(files_read_failed),
                "file_list": files_read_successfully,
            }
        )
        span_discovery.end()

        # Send discovery completion
        await self.ws_send({
            "type": "fix_step",
            "step": "discover",
            "status": "completed",
            "message": f"Found {len(files_read_successfully)} file(s) to analyze"
        })
        fix_steps[-1]["status"] = "completed"
        fix_steps[-1]["message"] = f"Found {len(files_read_successfully)} file(s) to analyze"

        if not file_contents:
            await self.ws_send({
                "type": "error",
                "message": "Could not read source files to fix error"
            })
            return

        # Build the prompt
        prompt = f"""\
You are an expert React/TypeScript developer. Fix the following error:

## Error
{error_message}
"""

        if error_file:
            prompt += f"\n**File:** {error_file}"
            if error_line:
                prompt += f":{error_line}"

        if error_stack:
            prompt += f"\n\n**Stack trace:**\n```\n{error_stack[:500]}\n```"

        prompt += "\n\n## Current Files\n"
        for path, content in file_contents.items():
            prompt += f"\n### {path}\n```\n{content}\n```\n"

        prompt += """
## Instructions

First, provide a brief explanation (2-3 sentences) of what's causing the error and how you'll fix it.

Then, provide the fix using the boltArtifact XML format. Only output files that need changes.

Example:
The error is caused by [reason]. I'll fix this by [solution].

<boltArtifact id="fix-error" title="Fix error">
  <boltAction type="file" filePath="path/to/file.tsx">
    Full corrected file content
  </boltAction>
</boltArtifact>

Rules:
1. Start with a brief explanation of the error and fix
2. Fix the reported error with minimal changes
3. Do NOT refactor unrelated code
4. Output complete file contents, not patches
5. Do NOT include shell actions
6. **CRITICAL**: Only use pre-installed packages (React, TypeScript, Vite, Tailwind CSS). Do NOT import other npm packages.
"""

        # Send generate step
        await self.ws_send({
            "type": "fix_step",
            "step": "generate",
            "status": "running",
            "message": "Generating fix with AI..."
        })
        fix_steps.append({
            "id": str(uuid.uuid4()),
            "step": "generate",
            "status": "running",
            "message": "Generating fix with AI..."
        })

        # Generate fix with LLM
        span_generate = langfuse_client.span(
            trace_id=self._trace_id,
            parent_observation_id=langfuse_context.get_current_observation_id(),
            name="generate-fix",
            metadata={
                "files_count": len(file_contents),
                "prompt_length": len(prompt),
            }
        )
        self._observation_id = span_generate.id

        try:
            generated_files: list[tuple[str, str]] = []
            parser = ActionParser(
                on_file_action=lambda p, c: generated_files.append((p, c)),
            )

            full_text: list[str] = []

            # Collect all LLM output first
            async for chunk in stream_chat(
                [{"role": "user", "content": "Fix the error."}],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("fix_error_direct")
            ):
                full_text.append(chunk)
                parser.feed(chunk)

            parser.flush()

            # Extract and send only the explanation (before the artifact)
            full_response = "".join(full_text)

            # Find where the artifact/xml starts
            artifact_start = full_response.find("<boltArtifact")
            xml_block_start = full_response.find("```xml")

            # Use whichever comes first (or neither)
            cut_point = len(full_response)
            if artifact_start != -1:
                cut_point = min(cut_point, artifact_start)
            if xml_block_start != -1:
                cut_point = min(cut_point, xml_block_start)

            # Send only the explanation part
            explanation = full_response[:cut_point].strip()
            if explanation:
                await self.ws_send({"type": "text", "content": explanation + "\n\n"})
                explanation_text = explanation

            # Update generate span with output
            span_generate.update(
                output={
                    "files_generated": len(generated_files),
                    "generated_file_paths": [p for p, _ in generated_files],
                    "response_length": sum(len(t) for t in full_text),
                }
            )
            span_generate.end()

            # Send generate completion
            await self.ws_send({
                "type": "fix_step",
                "step": "generate",
                "status": "completed",
                "message": f"Generated fix for {len(generated_files)} file(s)"
            })
            fix_steps[-1]["status"] = "completed"
            fix_steps[-1]["message"] = f"Generated fix for {len(generated_files)} file(s)"

            # Write files with a span
            if generated_files:
                # Send write step
                await self.ws_send({
                    "type": "fix_step",
                    "step": "write",
                    "status": "running",
                    "message": "Writing fixed files..."
                })
                fix_steps.append({
                    "id": str(uuid.uuid4()),
                    "step": "write",
                    "status": "running",
                    "message": "Writing fixed files..."
                })
                span_write = langfuse_client.span(
                    trace_id=self._trace_id,
                    parent_observation_id=langfuse_context.get_current_observation_id(),
                    name="write-fixed-files",
                    input={
                        "files_to_write": len(generated_files),
                        "file_paths": [p for p, _ in generated_files],
                    },
                )
                self._observation_id = span_write.id

                for path, content in generated_files:
                    await write_file(self.session_id, path, content)
                    await self.ws_send({"type": "file", "path": path, "content": content})

                span_write.update(
                    output={"success": True, "files_written": len(generated_files)}
                )
                span_write.end()

                # Send write completion
                await self.ws_send({
                    "type": "fix_step",
                    "step": "write",
                    "status": "completed",
                    "message": f"Wrote {len(generated_files)} file(s)"
                })
                fix_steps[-1]["status"] = "completed"
                fix_steps[-1]["message"] = f"Wrote {len(generated_files)} file(s)"

                logger.info("[agent] Fixed %d file(s) via direct error fix", len(generated_files))

                # Send validate step
                await self.ws_send({
                    "type": "fix_step",
                    "step": "validate",
                    "status": "running",
                    "message": "Validating fix..."
                })
                fix_steps.append({
                    "id": str(uuid.uuid4()),
                    "step": "validate",
                    "status": "running",
                    "message": "Validating fix..."
                })

                # Validate the fix by running build (already has @observe via _build)
                self._observation_id = langfuse_context.get_current_observation_id()
                errors = await self._build()

                if errors:
                    # Send validate failed
                    await self.ws_send({
                        "type": "fix_step",
                        "step": "validate",
                        "status": "failed",
                        "message": "Validation found issues"
                    })
                    fix_steps[-1]["status"] = "failed"
                    fix_steps[-1]["message"] = "Validation found issues"

                    # Send retry step
                    await self.ws_send({
                        "type": "fix_step",
                        "step": "retry",
                        "status": "running",
                        "message": "Attempting auto-fix..."
                    })
                    fix_steps.append({
                        "id": str(uuid.uuid4()),
                        "step": "retry",
                        "status": "running",
                        "message": "Attempting auto-fix..."
                    })

                    # Try one more fix iteration with a span
                    span_retry = langfuse_client.span(
                        trace_id=self._trace_id,
                        parent_observation_id=langfuse_context.get_current_observation_id(),
                        name="retry-fix-after-validation",
                        input={
                            "error_count": len(errors.split("\n")),
                            "error_preview": errors[:300],
                        },
                    )
                    self._observation_id = span_retry.id
                    self._completed_files = {p: c for p, c in generated_files}
                    await self._fix_errors(errors)
                    span_retry.update(output={"retry_completed": True})
                    span_retry.end()

                    # Send retry completion
                    await self.ws_send({
                        "type": "fix_step",
                        "step": "retry",
                        "status": "completed",
                        "message": "Auto-fix applied"
                    })
                    fix_steps[-1]["status"] = "completed"
                    fix_steps[-1]["message"] = "Auto-fix applied"
                else:
                    # Send validate success
                    await self.ws_send({
                        "type": "fix_step",
                        "step": "validate",
                        "status": "completed",
                        "message": "Fix validated successfully!"
                    })
                    fix_steps[-1]["status"] = "completed"
                    fix_steps[-1]["message"] = "Fix validated successfully!"

            # Save fix progress card to chat history
            if fix_steps:
                card_data = {
                    "type": "fix_progress",
                    "steps": fix_steps,
                }
                # Save the card with explanation as content (so it's searchable)
                await save_message(
                    self.project_id,
                    "assistant",
                    f"{explanation_text}\n\n{encode_card(card_data)}" if explanation_text else encode_card(card_data)
                )

            await self.ws_send({"type": "action_complete"})
            await self.ws_send({"type": "phase", "phase": "idle"})

        except Exception as exc:
            logger.exception("[agent] Direct error fix failed")
            span_generate.update(
                output={
                    "success": False,
                    "exception": str(exc),
                }
            )
            span_generate.end()
            await self.ws_send({
                "type": "error",
                "message": "Failed to fix error"
            })
            await self.ws_send({"type": "phase", "phase": "idle"})

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    async def _generate_summary(self) -> None:
        """Generate and persist a project summary after all tasks complete."""
        try:
            summary_input = json.dumps({
                "user_request": self._user_content,
                "architecture": self._architecture,
                "files_created": list(self._completed_files.keys()),
            }, indent=2)

            langfuse_context.update_current_observation(
                metadata={"files_count": len(self._completed_files)}
            )

            messages = [{"role": "user", "content": summary_input}]
            raw = await complete_chat(
                messages,
                SUMMARY_PROMPT,
                model=self.model,
                metadata=self._llm_metadata("generate_summary")
            )
            summary_data = _parse_json_response(raw)

            if summary_data:
                summary_json = json.dumps(summary_data, ensure_ascii=False)
                await update_project_summary(self.project_id, summary_json)
                await self.ws_send({"type": "project_summary", "summary": summary_data})
                logger.info("[agent] Project summary saved for %s", self.project_id)
        except Exception:
            logger.exception("[agent] Summary generation failed")

    # ------------------------------------------------------------------
    # Simple follow-up flow (existing behavior)
    # ------------------------------------------------------------------

    @observe(name="simple-follow-up", as_type="span")
    async def _simple_flow(self, content: str) -> None:
        """Single-turn AI flow for follow-up edits."""
        await self.ws_send({"type": "phase", "phase": "executing"})

        # Add follow-up metadata
        langfuse_context.update_current_observation(
            tags=["follow-up-edit"]
        )

        # Load project summary for context
        project = await get_project_by_session(self.session_id)
        summary_context = ""
        if project and project.summary:
            try:
                summary_data = json.loads(project.summary)
                summary_context = (
                    f"\n\n## Existing Project Summary\n"
                    f"{summary_data.get('summary', '')}\n"
                    f"Tech stack: {', '.join(summary_data.get('tech_stack', []))}\n"
                    f"Features: {', '.join(summary_data.get('features', []))}\n"
                )
            except (json.JSONDecodeError, AttributeError):
                pass

        history = await get_messages(self.project_id)
        # Filter out card messages from conversation context
        messages = [
            {"role": m.role, "content": m.content}
            for m in history
            if not m.content.startswith(CARD_PREFIX)
        ]

        full_response: list[str] = []
        pending_files: list[tuple[str, str]] = []
        pending_shells: list[str] = []

        parser = ActionParser(
            on_file_action=lambda p, c: pending_files.append((p, c)),
            on_shell_action=lambda c: pending_shells.append(c),
        )

        try:
            # Include package context (if any) as a leading user message.
            if self._package_id and self._package_results is not None:
                messages = [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "package_id": self._package_id,
                                "package_results": self._package_results,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                    *messages,
                ]

            system_prompt = get_system_prompt() + summary_context
            async for chunk in stream_chat(
                messages,
                system_prompt,
                model=self.model,
                metadata=self._llm_metadata("simple_follow_up")
            ):
                full_response.append(chunk)
                parser.feed(chunk)
                await self.ws_send({"type": "text", "content": chunk})

                for path, file_content in pending_files:
                    await write_file(self.session_id, path, file_content)
                    await self.ws_send({"type": "file", "path": path, "content": file_content})
                pending_files.clear()

                for command in pending_shells:
                    await self.ws_send({"type": "shell_output", "command": command, "output": "(skipped)"})
                pending_shells.clear()

        except Exception:
            logger.exception("[agent] Simple flow streaming failed")
            await self.ws_send({"type": "error", "message": "AI streaming failed"})
            return

        parser.flush()
        for path, file_content in pending_files:
            await write_file(self.session_id, path, file_content)
            await self.ws_send({"type": "file", "path": path, "content": file_content})

        assistant_content = "".join(full_response)
        await save_message(self.project_id, "assistant", assistant_content)
        await self.ws_send({"type": "phase", "phase": "complete"})
        await self.ws_send({"type": "action_complete"})

    async def _run_selected_package(self, package_id: str) -> dict:
        """Run a selected package via the Package API, returning results as JSON."""
        client = PackageApiClient(base_url=settings.PACKAGE_API_BASE_URL)
        try:
            # Use allQueries=true to match typical real runs.
            return await client.run_package(package_id, all_queries=True, body={})
        except PackageApiUpstreamError as e:
            raise RuntimeError(str(e)) from e


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

CARD_PREFIX = "<!--agent-card:"
CARD_SUFFIX = "-->"


def encode_card(card_data: dict) -> str:
    """Encode agent card data into a message content string."""
    return f"{CARD_PREFIX}{json.dumps(card_data, separators=(',', ':'))}{CARD_SUFFIX}"


def _parse_json_response(raw: str | None) -> dict:
    """Extract JSON from an AI response that may contain markdown fences."""
    if raw is None:
        logger.error("[agent] Received None response from LLM")
        return {}

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        logger.error("[agent] Failed to parse JSON from: %s", text[:200])
        return {}


def _dict_to_work_plan(data: dict, arch: dict, ux: dict) -> WorkPlan:
    """Convert a parsed JSON plan dict into a WorkPlan dataclass."""
    tasks = []
    for t in data.get("tasks", []):
        tasks.append(Task(
            id=t.get("id", f"task-{uuid.uuid4().hex[:6]}"),
            title=t.get("title", "Untitled task"),
            description=t.get("description", ""),
            files=t.get("files", []),
            depends_on=t.get("depends_on", []),
        ))
    return WorkPlan(
        id=f"plan-{uuid.uuid4().hex[:8]}",
        summary=data.get("summary", ""),
        architecture=arch,
        ux_design=ux,
        tasks=tasks,
    )
