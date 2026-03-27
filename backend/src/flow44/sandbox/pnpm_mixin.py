import logging
import os
import shutil
from abc import ABC

from pydantic import BaseModel

from flow44.config import settings
from flow44.sandbox.base import BaseSandbox

logger = logging.getLogger(__name__)


class BuildCommandResult(BaseModel):
    success: bool
    output: str
    errors: str


class PnpmMixin(BaseSandbox, ABC):
    # TODO: change to configure_npmrc
    def configure_npmrc(self) -> None:
        npmrc = os.path.join(self.workspace_dir, ".npmrc")
        with open(npmrc, "w", encoding="utf-8") as f:
            if settings.SANDBOX_MODE == "namespaced":
                f.write(f"store-dir={settings.stroe}\n")

    async def scaffold(self, template_dir: str) -> None:
        logger.info("Bootstrapping sandbox workspace for %s", self.project_id)
        shutil.copytree(template_dir, self.workspace_dir, dirs_exist_ok=True)

        self._stamp_vite_config(template_dir)

        async for line in self.exec("pnpm install 2>&1"):
            logger.info("[scaffold] %s", line.rstrip())

    def _stamp_vite_config(self, template_dir: str) -> None:
        template_path = os.path.join(template_dir, "vite.config.ts")
        with open(template_path, encoding="utf-8") as f:
            content = f.read()
        dest_path = os.path.join(self.workspace_dir, "vite.config.ts")
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content.replace("{{PROJECT_ID}}", self.project_id))

    # TODO: rename is_scaffold_complete or something?
    async def is_scaffolded(self) -> bool:
        # TODO: can make logic a bit smarter I guess...
        """Check if workspace has been scaffolded (package.json exists)."""
        package_json = os.path.join(self.workspace_dir, "package.json")
        return os.path.isfile(package_json)  # noqa: ASYNC240

    async def run_build_command(self, command: str) -> BuildCommandResult:
        """Run a build command (tsc/pnpm build/etc), detect errors, format output.

        Returns structured result with:
        - success: whether command succeeded
        - output: full command output
        - errors: formatted error messages (empty if success)
        """
        try:
            lines: list[str] = []
            async for line in self.exec(f"{command} 2>&1"):
                lines.append(line.rstrip())

            output = "\n".join(lines).strip()

            # Detect errors by patterns (since we don't get exit codes from exec generator)
            has_errors = bool(
                output
                and (
                    "error" in output.lower()
                    or "failed" in output.lower()
                    or "error TS" in output  # TypeScript specific
                )
            )

            if has_errors:
                formatted_errors = self._format_build_errors(output)
                return BuildCommandResult(success=False, output=output, errors=formatted_errors)

            return BuildCommandResult(success=True, output=output, errors="")

        except Exception as e:
            error_msg = f"Command '{command}' crashed: {e}"
            logger.exception("[pnpm] Build command failed: %s", command)
            return BuildCommandResult(success=False, output="", errors=error_msg)

    def _format_build_errors(self, raw_output: str) -> str:
        """Format build errors for LLM - currently returns raw output.

        Future enhancements:
        - Extract only error lines
        - Group by file
        - Remove ANSI codes (already handled by exec)
        - Summarize if too long
        """
        return raw_output

    async def start_dev_server(self) -> None:
        await self.stop_background_process("dev-server")

        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"

        cmd = f"pnpm dev --port {self.port} --strictPort --host 0.0.0.0"
        await self._spawn_background("dev-server", cmd, env)
        logger.info("Dev server started for %s on port %d", self.project_id, self.port)

    async def stop_dev_server(self) -> None:
        await self.stop_background_process("dev-server")

    def is_dev_server_running(self) -> bool:
        return self.is_background_process_running("dev-server")
