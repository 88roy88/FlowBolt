from __future__ import annotations

import logging
import uuid

from langfuse.decorators import observe

from flow44.ai.core.messages import Message
from flow44.ai.parser import ActionParser
from flow44.ai.prompts import render_fix_error_direct, render_fix_errors
from flow44.ai.provider import stream_chat
from flow44.sandbox.filesystem import list_files, read_file, write_file
from flow44.sandbox.manager import sandbox_manager

from ._base import BaseAgent

logger = logging.getLogger(__name__)


# TODO: we will probably make this into a ReAct agent like the follow up one.
class FixErrorAgent(BaseAgent):
    # TODO: make run abstract in the base class so all agents will be the same.
    # TODO: I like it that the run is the last function of the class and not the first :)
    @observe(name="fix-error-agent-run")
    async def run(
        self,
        error_message: str,
        error_file: str | None = None,
        error_line: int | None = None,
        error_stack: str | None = None,
    ) -> None:
        await self.emit({"type": "phase", "phase": "fixing"})
        fix_steps: list[dict] = []

        await self._send_step(fix_steps, "discover", "running", "Discovering files to fix...")
        file_contents = await self._discover_files(error_file)
        await self._send_step(fix_steps, "discover", "completed", f"Found {len(file_contents)} file(s) to analyze")

        if not file_contents:
            await self.emit({"type": "error", "message": "Could not read source files to fix error"})
            return

        await self._send_step(fix_steps, "generate", "running", "Generating fix with AI...")

        prompt = render_fix_error_direct(
            error_message=error_message,
            error_file=error_file,
            error_line=error_line,
            error_stack=error_stack,
            files=file_contents,
        )

        generated_files: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: generated_files.append((p, c)))
        full_text: list[str] = []

        try:
            async for chunk in stream_chat(
                [Message.user("Fix the error.")],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("fix_error_direct"),
            ):
                full_text.append(chunk)
                parser.feed(chunk)
            parser.flush()
        except Exception:
            logger.exception("[fix-error] Generation failed")
            await self.emit({"type": "error", "message": "Failed to fix error"})
            await self.emit({"type": "phase", "phase": "idle"})
            return

        full_response = "".join(full_text)
        artifact_start = full_response.find("<flowArtifact")
        cut = artifact_start if artifact_start != -1 else len(full_response)
        explanation = full_response[:cut].strip()
        if explanation:
            await self.emit({"type": "text", "content": explanation + "\n\n"})

        await self._send_step(fix_steps, "generate", "completed", f"Generated fix for {len(generated_files)} file(s)")

        if generated_files:
            await self._send_step(fix_steps, "write", "running", "Writing fixed files...")
            for path, content in generated_files:
                await write_file(self.session_id, path, content)
                await self.emit({"type": "file", "path": path, "content": content})
            await self._send_step(fix_steps, "write", "completed", f"Wrote {len(generated_files)} file(s)")

            await self._send_step(fix_steps, "validate", "running", "Validating fix...")
            errors = await self._build()

            if errors:
                await self._send_step(fix_steps, "validate", "failed", "Validation found issues")
                await self._send_step(fix_steps, "retry", "running", "Attempting auto-fix...")
                await self._retry_fix(errors, dict(generated_files))
                await self._send_step(fix_steps, "retry", "completed", "Auto-fix applied")
            else:
                await self._send_step(fix_steps, "validate", "completed", "Fix validated successfully!")

        await self.emit({"type": "action_complete"})
        await self.emit({"type": "phase", "phase": "idle"})

    # TODO: this is probably redundant now. we can use the emit.
    async def _send_step(self, steps: list[dict], step: str, status: str, message: str) -> None:
        await self.emit({"type": "fix_step", "step": step, "status": status, "message": message})
        for s in steps:
            if s["step"] == step:
                s["status"] = status
                s["message"] = message
                return
        steps.append({"id": str(uuid.uuid4()), "step": step, "status": status, "message": message})

    # TODO: add the some AI magic to this function if the file is not clear or need more?
    # TODO: should ignore stuff from node_models? and stuff like that?
    async def _discover_files(self, error_file: str | None) -> dict[str, str]:
        files_to_read: list[str] = []

        if error_file:
            files_to_read.append(self._normalize_path(error_file))
        else:
            try:
                tree = await list_files(self.session_id)
                for entry in tree:
                    if entry.name == "src" and entry.children:
                        for child in entry.children:
                            if child.path.endswith((".tsx", ".ts", ".jsx", ".js")):
                                files_to_read.append(child.path)
            except Exception:
                logger.warning("[fix-error] Could not read file tree")

        file_contents: dict[str, str] = {}
        for path in files_to_read[:10]:
            try:
                file_contents[path] = await read_file(self.session_id, path)
            except Exception:
                logger.warning("[fix-error] Could not read %s", path)
                if not file_contents and error_file:
                    try:
                        tree = await list_files(self.session_id)
                        for entry in tree:
                            if entry.name == "src" and entry.children:
                                for child in entry.children:
                                    if child.path.endswith((".tsx", ".ts", ".jsx", ".js", ".css")):
                                        try:
                                            file_contents[child.path] = await read_file(self.session_id, child.path)
                                        except Exception:
                                            logger.debug("Could not read fallback file %s", child.path)
                                break
                    except Exception:
                        logger.debug("Fallback file tree listing failed")
        return file_contents

    # TODO: we might want genral utils outside of the agent. also, me might want to move this to the sandbox manager.
    # TODO: or even to the frontend
    def _normalize_path(self, path: str) -> str:
        if f"/{self.session_id}/" in path:
            idx = path.find(f"/{self.session_id}/")
            path = path[idx + len(self.session_id) + 2 :]
            if not path.startswith("/"):
                path = "/" + path
        elif not path.startswith("/src/"):
            if "/src/" in path:
                path = path[path.rfind("/src/") :]
            elif not path.startswith("/"):
                path = "/src/" + path
            else:
                path = "/src" + path
        return path

    # TODO: seems like a repeating function? make common?
    async def _build(self) -> str:
        try:
            lines: list[str] = []
            async for line in sandbox_manager.get_sandbox(self.session_id).exec("pnpm build 2>&1"):
                lines.append(line.rstrip())
            output = "\n".join(lines).strip()
            return output if output and ("error" in output.lower() or "failed" in output.lower()) else ""
        except Exception:
            logger.exception("[fix-error] Build failed")
            return ""

    async def _retry_fix(self, errors: str, completed_files: dict[str, str]) -> None:
        prompt = render_fix_errors(errors=errors, files=completed_files)
        generated: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))
        try:
            async for chunk in stream_chat(
                [Message.user("Fix the TypeScript errors.")],
                prompt,
                model=self.model,
                metadata=self._llm_metadata("fix_error_retry"),
            ):
                parser.feed(chunk)
            parser.flush()
            for path, content in generated:
                await write_file(self.session_id, path, content)
                await self.emit({"type": "file", "path": path, "content": content})
        except Exception:
            logger.exception("[fix-error] Retry fix failed")
