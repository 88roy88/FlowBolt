import logging
import os
import shutil
from abc import ABC

from pydantic import BaseModel

from flow44.config import settings
from flow44.paths import preview_base_path, sandbox_path_env, set_index_base_href
from flow44.sandbox.base import BaseSandbox

logger = logging.getLogger(__name__)


class BuildCommandResult(BaseModel):
    success: bool
    output: str
    errors: str


class PnpmMixin(BaseSandbox, ABC):
    _ROUTING_STUB_DIR = "routing-stub"

    # TODO: change to configure_npmrc
    def configure_npmrc(self) -> None:
        npmrc = os.path.join(self.workspace_dir, ".npmrc")
        existing_content = ""
        if os.path.exists(npmrc):
            with open(npmrc, encoding="utf-8") as f:
                existing_content = f.read()

        # Ensure store-dir is set so pnpm uses the correct volume path
        if "store-dir" not in existing_content:
            store_path = "/.pnpm-store" if settings.SANDBOX_MODE == "namespaced" else settings.PNPM_STORE_DIR
            with open(npmrc, "a", encoding="utf-8") as f:
                if existing_content and not existing_content.endswith("\n"):
                    f.write("\n")
                f.write(f"store-dir={store_path}\n")

    async def scaffold(self, template_dir: str) -> None:
        logger.info("Bootstrapping sandbox workspace for %s", self.project_id)
        shutil.copytree(
            template_dir,
            self.workspace_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(self._ROUTING_STUB_DIR),
        )

        self._stamp_vite_config(template_dir)
        self._configure_preview_paths()
        self.configure_npmrc()

        async for line in self.exec("pnpm install 2>&1"):
            logger.info("[scaffold] %s", line.rstrip())

    def _has_client_routing(self) -> bool:
        router_file = os.path.join(self.workspace_dir, "src", "router", "AppRouter.tsx")
        return os.path.isfile(router_file)

    async def enable_client_routing(self, template_dir: str) -> None:
        """Install react-router-dom and copy the fixed AppRouter stub into the workspace."""
        if self._has_client_routing():
            return

        async for line in self.exec("pnpm add react-router-dom 2>&1"):
            logger.info("[routing] %s", line.rstrip())

        stub_src = os.path.join(template_dir, self._ROUTING_STUB_DIR)
        dest = os.path.join(self.workspace_dir, "src", "router")
        os.makedirs(dest, exist_ok=True)
        for name in os.listdir(stub_src):
            shutil.copy2(os.path.join(stub_src, name), os.path.join(dest, name))

    def _stamp_vite_config(self, template_dir: str) -> None:
        template_path = os.path.join(template_dir, "vite.config.ts")
        with open(template_path, encoding="utf-8") as f:
            content = f.read()
        content = self._apply_vite_config_stamps(content)
        dest_path = os.path.join(self.workspace_dir, "vite.config.ts")
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _apply_vite_config_stamps(self, content: str) -> str:
        return (
            content.replace("{{AUTH_PROVIDER_URL}}", settings.SANDBOX_AUTH_PROVIDER_URL)
            .replace("{{AUTH_STORAGE_KEY}}", settings.SANDBOX_AUTH_STORAGE_KEY)
            .replace("{{AUTH_USE_IFRAME}}", str(settings.SANDBOX_AUTH_USE_IFRAME).lower())
        )

    def refresh_vite_config_stamps(self) -> None:
        """Re-apply Flow44 env stamps to workspace vite.config.ts (e.g. before publish build)."""
        vite_path = os.path.join(self.workspace_dir, "vite.config.ts")
        if not os.path.isfile(vite_path):
            return
        with open(vite_path, encoding="utf-8") as handle:
            content = handle.read()
        with open(vite_path, "w", encoding="utf-8") as handle:
            handle.write(self._apply_vite_config_stamps(content))

    def _configure_preview_paths(self) -> None:
        set_index_base_href(self.workspace_dir, preview_base_path(self.project_id))
        self._write_sandbox_env_file(".env.local")

    def _write_sandbox_env_file(self, filename: str) -> None:
        env_path = os.path.join(self.workspace_dir, filename)
        env_vars = sandbox_path_env(self.project_id, api_base_url=settings.EXPORT_API_BASE_URL)
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(f"{key}={value}" for key, value in env_vars.items()) + "\n")

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

        self._configure_preview_paths()
        env = os.environ.copy()
        env.update(sandbox_path_env(self.project_id, api_base_url=settings.EXPORT_API_BASE_URL))
        env["FORCE_COLOR"] = "1"

        cmd = f"pnpm dev --port {self.port} --strictPort --host 0.0.0.0"
        await self._spawn_background("dev-server", cmd, env)
        logger.info("Dev server started for %s on port %d", self.project_id, self.port)

    async def stop_dev_server(self) -> None:
        await self.stop_background_process("dev-server")

    def is_dev_server_running(self) -> bool:
        return self.is_background_process_running("dev-server")
