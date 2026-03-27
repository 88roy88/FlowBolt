import logging
import uuid
from pathlib import PurePosixPath
from typing import Any

from langfuse.decorators import observe
from pydantic_ai import Agent

from flow44.ai.parser import ActionParser
from flow44.ai.agents.fix_error.prompts import render_fix_error_direct, render_fix_errors

from flow44.ai.agents._base import BaseAgent, resolve_model

logger = logging.getLogger(__name__)

_fix_agent: Agent[None, str] = Agent()


class FixErrorAgent(BaseAgent):
    @observe(name="fix-error-agent-run")  # type: ignore[untyped-decorator]
    async def run(
        self,
        error_message: str,
        error_file: str | None = None,
        error_line: int | None = None,
        error_stack: str | None = None,
    ) -> None:
        model = resolve_model(self.model)
        await self.emit({"type": "phase", "phase": "fixing"})
        fix_steps: list[dict[str, Any]] = []

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
            async with _fix_agent.run_stream(
                "Fix the error.",
                instructions=prompt,
                model=model,
            ) as stream:
                async for chunk in stream.stream_text(delta=True):
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
                await self.sandbox.write_file(path, content)
                await self.emit({"type": "file", "path": path, "content": content})
            await self._send_step(fix_steps, "write", "completed", f"Wrote {len(generated_files)} file(s)")

            await self._send_step(fix_steps, "validate", "running", "Validating fix...")
            errors = await self._build()

            if errors:
                await self._send_step(fix_steps, "validate", "failed", "Validation found issues")
                await self._send_step(fix_steps, "retry", "running", "Attempting auto-fix...")
                await self._retry_fix(errors, dict(generated_files), model)
                await self._send_step(fix_steps, "retry", "completed", "Auto-fix applied")
            else:
                await self._send_step(fix_steps, "validate", "completed", "Fix validated successfully!")

        await self.emit({"type": "action_complete"})
        await self.emit({"type": "phase", "phase": "idle"})

    async def _send_step(self, steps: list[dict[str, Any]], step: str, status: str, message: str) -> None:
        await self.emit({"type": "fix_step", "step": step, "status": status, "message": message})
        for s in steps:
            if s["step"] == step:
                s["status"] = status
                s["message"] = message
                return
        steps.append({"id": str(uuid.uuid4()), "step": step, "status": status, "message": message})

    async def _discover_files(self, error_file: str | None) -> dict[str, str]:  # noqa: C901, PLR0912
        files_to_read: list[str] = []

        if error_file:
            files_to_read.append(self._normalize_path(error_file))
        else:
            try:
                tree = await self.sandbox.list_files()
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
                file_contents[path] = await self.sandbox.read_file(path)
            except Exception:
                logger.warning("[fix-error] Could not read %s", path)
                if not file_contents and error_file:
                    try:
                        tree = await self.sandbox.list_files()
                        for entry in tree:
                            if entry.name == "src" and entry.children:
                                for child in entry.children:
                                    if child.path.endswith((".tsx", ".ts", ".jsx", ".js", ".css")):
                                        try:
                                            file_contents[child.path] = await self.sandbox.read_file(child.path)
                                        except Exception:
                                            logger.debug("Could not read fallback file %s", child.path)
                                break
                    except Exception:
                        logger.debug("Fallback file tree listing failed")
        return file_contents

    def _normalize_path(self, path: str) -> str:
        """Extract a workspace-relative path from an absolute or mangled error path."""
        parts = PurePosixPath(path.replace("\\", "/")).parts

        if self.project_id in parts:
            idx = parts.index(self.project_id)
            parts = parts[idx + 1 :]

        if "src" in parts:
            idx = parts.index("src")
            return str(PurePosixPath(*parts[idx:]))

        return str(PurePosixPath("src", *parts))

    async def _build(self) -> str:
        result = await self.sandbox.run_build_command("pnpm build")
        return result.errors

    async def _retry_fix(self, errors: str, completed_files: dict[str, str], model: str | None) -> None:
        prompt = render_fix_errors(errors=errors, files=completed_files)
        generated: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))
        try:
            async with _fix_agent.run_stream(
                "Fix the TypeScript errors.",
                instructions=prompt,
                model=model,
            ) as stream:
                async for chunk in stream.stream_text(delta=True):
                    parser.feed(chunk)
            parser.flush()
            for path, content in generated:
                await self.sandbox.write_file(path, content)
                await self.emit({"type": "file", "path": path, "content": content})
        except Exception:
            logger.exception("[fix-error] Retry fix failed")
