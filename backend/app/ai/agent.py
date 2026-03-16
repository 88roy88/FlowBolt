"""Multi-phase agent orchestrator.

Routes user messages through: classify → design → plan → approve → execute.
Follow-up edits bypass the agent and use the existing single-turn flow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from collections.abc import Callable, Awaitable

from app.ai.parser import ActionParser
from app.ai.provider import complete_chat, stream_chat
from app.ai.task_tree import Task, WorkPlan
from app.ai.prompts import (
    CLASSIFY_PROMPT,
    ARCHITECTURE_PROMPT,
    UX_DESIGN_PROMPT,
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
        self.work_plan: WorkPlan | None = None
        self.model: str | None = None
        self._completed_files: dict[str, str] = {}
        self._user_content: str = ""

    async def handle_message(
        self,
        content: str,
        model: str | None = None,
    ) -> None:
        """Process a new user message through the agent pipeline."""
        self.model = model
        self._user_content = content

        # 1. Classify
        await self.ws_send({"type": "phase", "phase": "classifying"})
        is_new = await self._classify(content)

        if not is_new:
            await self._simple_flow(content)
            return

        # 2. Design (parallel)
        await self.ws_send({"type": "phase", "phase": "designing"})
        arch, ux = await asyncio.gather(
            self._design_architecture(content),
            self._design_ux(content),
        )

        # 3. Build work plan
        await self.ws_send({"type": "phase", "phase": "planning"})
        self.work_plan = await self._build_work_plan(arch, ux, content)

        # 4. Present to user
        self.state = "awaiting_approval"
        await self.ws_send({"type": "phase", "phase": "awaiting_approval"})
        await self.ws_send({"type": "work_plan", "plan": _plan_to_dict(self.work_plan)})

    async def handle_plan_response(
        self,
        action: str,
        feedback: str | None = None,
    ) -> None:
        """Handle user's response to the work plan."""
        if action == "accept":
            await self._execute()
        elif action == "modify":
            if self.work_plan and feedback:
                await self.ws_send({"type": "phase", "phase": "planning"})
                self.work_plan = await self._rebuild_work_plan_with_feedback(feedback)
                self.state = "awaiting_approval"
                await self.ws_send({"type": "phase", "phase": "awaiting_approval"})
                await self.ws_send({"type": "work_plan", "plan": _plan_to_dict(self.work_plan)})
        elif action == "reject":
            self.state = "idle"
            self.work_plan = None
            await self.ws_send({"type": "phase", "phase": "idle"})

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    async def _classify(self, content: str) -> bool:
        """Return True if this is a new project request, False for follow-up."""
        history = await get_messages(self.project_id)
        # First message is almost always a new project
        assistant_msgs = [m for m in history if m.role == "assistant"]
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
    # Design phase
    # ------------------------------------------------------------------

    async def _design_architecture(self, content: str) -> dict:
        """Run the architecture design AI call."""
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
        """Run the UI/UX design AI call."""
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
    # Planning
    # ------------------------------------------------------------------

    async def _build_work_plan(self, arch: dict, ux: dict, content: str) -> WorkPlan:
        """Merge designs into a work plan via AI."""
        merge_input = json.dumps({
            "user_request": content,
            "architecture": arch,
            "ux_design": ux,
        }, indent=2)
        messages = [{"role": "user", "content": merge_input}]
        raw = await complete_chat(messages, MERGE_PROMPT, model=self.model)
        plan_data = _parse_json_response(raw)
        return _dict_to_work_plan(plan_data, arch, ux)

    async def _rebuild_work_plan_with_feedback(self, feedback: str) -> WorkPlan:
        """Re-run planning with user feedback on the existing plan."""
        assert self.work_plan is not None
        merge_input = json.dumps({
            "user_request": self._user_content,
            "architecture": self.work_plan.architecture,
            "ux_design": self.work_plan.ux_design,
            "previous_plan": {
                "summary": self.work_plan.summary,
                "tasks": [{"id": t.id, "title": t.title, "files": t.files} for t in self.work_plan.tasks],
            },
            "user_feedback": feedback,
        }, indent=2)
        messages = [{"role": "user", "content": merge_input}]
        raw = await complete_chat(
            messages,
            MERGE_PROMPT + "\n\nThe user has provided feedback on a previous plan. "
            "Incorporate their feedback and produce an updated plan.",
            model=self.model,
        )
        plan_data = _parse_json_response(raw)
        return _dict_to_work_plan(plan_data, self.work_plan.architecture, self.work_plan.ux_design)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute(self) -> None:
        """Execute the work plan layer by layer."""
        assert self.work_plan is not None
        self.state = "executing"
        await self.ws_send({"type": "phase", "phase": "executing"})

        self._completed_files = {}
        layers = self.work_plan.execution_layers()

        for layer in layers:
            await asyncio.gather(
                *[self._execute_task(task) for task in layer]
            )

        # Save a summary as the assistant message
        file_list = "\n".join(f"- {p}" for p in self._completed_files.keys())
        summary = f"Built the project based on the approved plan.\n\nFiles created:\n{file_list}"
        await save_message(self.project_id, "assistant", summary)

        self.state = "idle"
        self.work_plan = None
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

        assert self.work_plan is not None
        prompt = get_codegen_prompt(
            task_title=task.title,
            task_description=task.description,
            task_files=task.files,
            architecture=self.work_plan.architecture,
            ux_design=self.work_plan.ux_design,
            completed_files=self._completed_files if self._completed_files else None,
        )

        try:
            # Collect the full streamed response, parse files from it
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

            # Process any final files
            for path, content in generated_files:
                await write_file(self.session_id, path, content)
                self._completed_files[path] = content
                await self.ws_send({
                    "type": "task_update",
                    "taskId": task.id,
                    "status": "running",
                    "file": path,
                })
                # Also send file event for the editor
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
        messages = [{"role": m.role, "content": m.content} for m in history]

        full_response: list[str] = []
        pending_files: list[tuple[str, str]] = []
        pending_shells: list[str] = []

        parser = ActionParser(
            on_file_action=lambda p, c: pending_files.append((p, c)),
            on_shell_action=lambda c: pending_shells.append(c),
        )

        try:
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


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_json_response(raw: str) -> dict:
    """Extract JSON from an AI response that may contain markdown fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines[1:] if l.strip() != "```"]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
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


def _plan_to_dict(plan: WorkPlan) -> dict:
    """Convert a WorkPlan to a JSON-serializable dict for the frontend."""
    return {
        "id": plan.id,
        "summary": plan.summary,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "files": t.files,
                "dependsOn": t.depends_on,
                "status": t.status,
            }
            for t in plan.tasks
        ],
    }
