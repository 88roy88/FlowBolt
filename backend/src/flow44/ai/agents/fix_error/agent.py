import logging
from pathlib import PurePosixPath

from langfuse.decorators import observe

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.fix_error.fix_error_state import FixErrorState
from flow44.ai.agents.fix_error.prompts import render_fix_error_direct, render_fix_errors
from flow44.ai.core.flow import Flow
from flow44.ai.core.messages import Message
from flow44.ai.core.provider import stream_chat
from flow44.ai.parser import ActionParser
from flow44.sandbox.main import PnpmSandbox

logger = logging.getLogger(__name__)


MAX_RETRY_ATTEMPTS = 1


class FixErrorAgent(BaseAgent):
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(project_id, sandbox, model=model, trace_id=trace_id)
        self._flow = self._build_flow()

    def _build_flow(self) -> Flow[FixErrorState]:
        """Build the fix error flow with explicit steps and routing."""
        flow = Flow[FixErrorState]("fix_error")

        flow.add_step("discover", self._step_discover, next_step="generate")
        flow.add_step("generate", self._step_generate, next_step="write")
        flow.add_step("write", self._step_write, next_step="validate")
        flow.add_step("validate", self._step_validate, next_step=self._route_after_validate)
        flow.add_step("retry", self._step_retry, next_step="validate")
        flow.add_step("complete", self._step_complete, next_step=None)

        return flow

    def _route_after_validate(self, state: FixErrorState) -> str | None:
        """Route after validation: retry, or complete."""
        if not state.validation_errors:
            return "complete"

        if state.retry_count >= MAX_RETRY_ATTEMPTS:
            logger.warning("[fix-error] Max retry attempts reached")
            return "complete"

        return "retry"

    @observe(name="fix-error-agent-run")  # type: ignore[untyped-decorator]
    async def run(
        self,
        error_message: str,
        error_file: str | None = None,
        error_line: int | None = None,
        error_stack: str | None = None,
    ) -> None:
        await self.emit({"type": "phase", "phase": "fixing"})

        # Initialize fix error state for Flow
        fix_state = FixErrorState(
            project_id=self.project_id,
            sandbox_ref=self.sandbox,
            emit_fn=self.emit,
            model=self.model,
            llm_metadata_fn=self._llm_metadata,
            error_message=error_message,
            error_file=error_file,
            error_line=error_line,
            error_stack=error_stack,
        )

        # Run the flow
        await self._flow.run(fix_state, start="discover")

    # -- Flow Steps --

    async def _step_discover(self, state: FixErrorState) -> FixErrorState:
        """Step: Discover files to fix."""
        await state.emit_fn(
            {"type": "fix_step", "step": "discover", "status": "running", "message": "Discovering files to fix..."}
        )

        state.discovered_files = await self._discover_files(state.error_file)

        if not state.discovered_files:
            await state.emit_fn({"type": "error", "message": "Could not read source files to fix error"})
            await state.emit_fn({"type": "phase", "phase": "idle"})
            raise RuntimeError("No files discovered")

        await state.emit_fn(
            {
                "type": "fix_step",
                "step": "discover",
                "status": "completed",
                "message": f"Found {len(state.discovered_files)} file(s) to analyze",
            }
        )

        return state

    async def _step_generate(self, state: FixErrorState) -> FixErrorState:
        """Step: Generate fix with AI."""
        await state.emit_fn(
            {"type": "fix_step", "step": "generate", "status": "running", "message": "Generating fix with AI..."}
        )

        prompt = render_fix_error_direct(
            error_message=state.error_message,
            error_file=state.error_file,
            error_line=state.error_line,
            error_stack=state.error_stack,
            files=state.discovered_files,
        )

        parser = ActionParser(on_file_action=lambda p, c: state.generated_files.append((p, c)))
        full_text: list[str] = []

        try:
            async for chunk in stream_chat(
                [Message.user("Fix the error.")],
                prompt,
                model=state.model,
                metadata=state.llm_metadata_fn("fix_error_direct"),
            ):
                full_text.append(chunk)
                parser.feed(chunk)
            parser.flush()
        except Exception:
            logger.exception("[fix-error] Generation failed")
            await state.emit_fn({"type": "error", "message": "Failed to fix error"})
            await state.emit_fn({"type": "phase", "phase": "idle"})
            raise

        state.full_response = "".join(full_text)
        artifact_start = state.full_response.find("<flowArtifact")
        cut = artifact_start if artifact_start != -1 else len(state.full_response)
        explanation = state.full_response[:cut].strip()
        if explanation:
            await state.emit_fn({"type": "text", "content": explanation + "\n\n"})

        await state.emit_fn(
            {
                "type": "fix_step",
                "step": "generate",
                "status": "completed",
                "message": f"Generated fix for {len(state.generated_files)} file(s)",
            }
        )

        return state

    async def _step_write(self, state: FixErrorState) -> FixErrorState:
        """Step: Write generated files."""
        if not state.generated_files:
            return state

        await state.emit_fn(
            {"type": "fix_step", "step": "write", "status": "running", "message": "Writing fixed files..."}
        )

        for path, content in state.generated_files:
            await state.sandbox_ref.write_file(path, content)
            await state.emit_fn({"type": "file", "path": path, "content": content})

        await state.emit_fn(
            {
                "type": "fix_step",
                "step": "write",
                "status": "completed",
                "message": f"Wrote {len(state.generated_files)} file(s)",
            }
        )

        return state

    async def _step_validate(self, state: FixErrorState) -> FixErrorState:
        """Step: Validate the fix."""
        if not state.generated_files:
            return state

        await state.emit_fn(
            {"type": "fix_step", "step": "validate", "status": "running", "message": "Validating fix..."}
        )

        state.validation_errors = await self._build()

        if state.validation_errors:
            await state.emit_fn(
                {"type": "fix_step", "step": "validate", "status": "failed", "message": "Validation found issues"}
            )
        else:
            await state.emit_fn(
                {
                    "type": "fix_step",
                    "step": "validate",
                    "status": "completed",
                    "message": "Fix validated successfully!",
                }
            )

        return state

    async def _step_retry(self, state: FixErrorState) -> FixErrorState:
        """Step: Retry fix with errors."""
        state.retry_count += 1

        await state.emit_fn(
            {"type": "fix_step", "step": "retry", "status": "running", "message": "Attempting auto-fix..."}
        )

        prompt = render_fix_errors(errors=state.validation_errors, files=dict(state.generated_files))
        generated: list[tuple[str, str]] = []
        parser = ActionParser(on_file_action=lambda p, c: generated.append((p, c)))

        try:
            async for chunk in stream_chat(
                [Message.user("Fix the TypeScript errors.")],
                prompt,
                model=state.model,
                metadata=state.llm_metadata_fn("fix_error_retry"),
            ):
                parser.feed(chunk)
            parser.flush()

            for path, content in generated:
                await state.sandbox_ref.write_file(path, content)
                await state.emit_fn({"type": "file", "path": path, "content": content})

            # Update generated files list
            state.generated_files = generated

            await state.emit_fn(
                {"type": "fix_step", "step": "retry", "status": "completed", "message": "Auto-fix applied"}
            )
        except Exception:
            logger.exception("[fix-error] Retry fix failed")
            await state.emit_fn({"type": "fix_step", "step": "retry", "status": "failed", "message": "Auto-fix failed"})

        return state

    async def _step_complete(self, state: FixErrorState) -> FixErrorState:
        """Step: Complete the fix process."""
        await state.emit_fn({"type": "action_complete"})
        await state.emit_fn({"type": "phase", "phase": "idle"})
        return state

    # -- Helper Methods --

    # TODO: add the some AI magic to this function if the file is not clear or need more?
    # TODO: should ignore stuff from node_models? and stuff like that?
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

    # TODO: we might want genral utils outside of the agent. also, me might want to move this to the sandbox manager.
    # TODO: or even to the frontend
    def _normalize_path(self, path: str) -> str:
        """Extract a workspace-relative path from an absolute or mangled error path."""
        # Normalize to posix (error messages may contain either separator)
        parts = PurePosixPath(path.replace("\\", "/")).parts

        # Strip workspace prefix: /var/lib/.../project_id/src/App.tsx → src/App.tsx
        if self.project_id in parts:
            idx = parts.index(self.project_id)
            parts = parts[idx + 1 :]

        # Extract from src/ onward
        if "src" in parts:
            idx = parts.index("src")
            return str(PurePosixPath(*parts[idx:]))

        return str(PurePosixPath("src", *parts))

    async def _build(self) -> str:
        result = await self.sandbox.run_build_command("pnpm build")
        return result.errors
