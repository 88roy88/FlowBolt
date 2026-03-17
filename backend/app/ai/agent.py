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
from app.ai.parser import ActionParser
from app.ai.provider import complete_chat, stream_chat
from app.ai.task_tree import Task, WorkPlan
from app.ai.prompts import (
    CLASSIFY_PROMPT,
    ARCHITECTURE_PROMPT,
    UX_DESIGN_PROMPT,
    USER_PLAN_PROMPT,
    MERGE_PROMPT,
    get_codegen_prompt,
)
from app.ai.prompts_legacy import get_system_prompt
from app.models.chat import get_messages, save_message
from app.sandbox.filesystem import write_file

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
            # Build the technical plan internally, then execute
            await self.ws_send({"type": "phase", "phase": "planning"})
            self._work_plan = await self._build_technical_plan()
            # Send task list for progress UI (titles only, no file paths)
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
            return True

        messages = [{"role": "user", "content": content}]
        try:
            raw = await complete_chat(messages, CLASSIFY_PROMPT, model=self.model)
            data = json.loads(raw.strip())
            classification = data.get("classification", "follow_up")
            logger.info("[agent] Classification: %s", classification)
            return classification == "new_project"
        except Exception:
            logger.exception("[agent] Classification failed, defaulting to follow_up")
            return False

    # ------------------------------------------------------------------
    # Design phase (internal)
    # ------------------------------------------------------------------

    async def _design_architecture(self, content: str) -> dict:
        messages = [{"role": "user", "content": content}]
        try:
            raw = await complete_chat(messages, ARCHITECTURE_PROMPT, model=self.model)
            await self.ws_send({"type": "design_progress", "stream": "architecture", "content": "complete"})
            return _parse_json_response(raw)
        except Exception:
            logger.exception("[agent] Architecture design failed")
            await self.ws_send({"type": "design_progress", "stream": "architecture", "content": "failed"})
            return {}

    async def _design_ux(self, content: str) -> dict:
        messages = [{"role": "user", "content": content}]
        try:
            raw = await complete_chat(messages, UX_DESIGN_PROMPT, model=self.model)
            await self.ws_send({"type": "design_progress", "stream": "ux", "content": "complete"})
            return _parse_json_response(raw)
        except Exception:
            logger.exception("[agent] UX design failed")
            await self.ws_send({"type": "design_progress", "stream": "ux", "content": "failed"})
            return {}

    # ------------------------------------------------------------------
    # User-facing overview
    # ------------------------------------------------------------------

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
        raw = await complete_chat(messages, USER_PLAN_PROMPT, model=self.model)
        return _parse_json_response(raw)

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
        raw = await complete_chat(messages, MERGE_PROMPT, model=self.model)
        plan_data = _parse_json_response(raw)
        return _dict_to_work_plan(plan_data, self._architecture, self._ux_design)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute(self) -> None:
        """Execute the technical plan layer by layer."""
        assert self._work_plan is not None
        self.state = "executing"
        await self.ws_send({"type": "phase", "phase": "executing"})

        self._completed_files = {}
        layers = self._work_plan.execution_layers()

        for layer in layers:
            await asyncio.gather(
                *[self._execute_task(task) for task in layer]
            )

        # Save task progress card
        await save_message(self.project_id, "assistant", encode_card({
            "type": "task_progress",
            "tasks": [
                {"id": t.id, "title": t.title, "status": t.status}
                for t in self._work_plan.tasks
            ],
        }))

        self.state = "idle"
        self._work_plan = None
        await self.ws_send({"type": "phase", "phase": "complete"})
        await self.ws_send({"type": "action_complete"})

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task: call AI for code, parse XML, write files."""
        task.status = "running"
        await self.ws_send({
            "type": "task_update",
            "taskId": task.id,
            "status": "running",
        })

        assert self._work_plan is not None
        prompt = get_codegen_prompt(
            task_title=task.title,
            task_description=task.description,
            task_files=task.files,
            architecture=self._work_plan.architecture,
            ux_design=self._work_plan.ux_design,
            package_data=self._package_results,
            completed_files=self._completed_files if self._completed_files else None,
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
            ):
                full_text.append(chunk)
                parser.feed(chunk)

            parser.flush()

            for path, content in generated_files:
                await write_file(self.session_id, path, content)
                self._completed_files[path] = content
                await self.ws_send({
                    "type": "task_update",
                    "taskId": task.id,
                    "status": "running",
                    "file": path,
                })
                await self.ws_send({"type": "file", "path": path, "content": content})

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
    # Simple follow-up flow (existing behavior)
    # ------------------------------------------------------------------

    async def _simple_flow(self, content: str) -> None:
        """Single-turn AI flow for follow-up edits."""
        await self.ws_send({"type": "phase", "phase": "executing"})

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
            async for chunk in stream_chat(messages, get_system_prompt(), model=self.model):
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


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from an AI response that may contain markdown fences."""
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
