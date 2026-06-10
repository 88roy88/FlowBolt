import json
import logging
import os
import shlex
import shutil
from abc import ABC

from pydantic import BaseModel

from flow44.config import settings
from flow44.paths import preview_base_path, sandbox_path_env
from flow44.sandbox.base import BaseSandbox

logger = logging.getLogger(__name__)


class BuildCommandResult(BaseModel):
    success: bool
    output: str
    errors: str


class PnpmMixin(BaseSandbox, ABC):
    def configure_npmrc(self) -> None:
        npmrc = os.path.join(self.workspace_dir, ".npmrc")
        store_path = "/.pnpm-store" if settings.SANDBOX_MODE == "namespaced" else settings.PNPM_STORE_DIR

        content = (
            f"registry={settings.NPM_REGISTRY}\n"
            f"strict-ssl={str(settings.NPM_STRICT_SSL).lower()}\n"
            f"audit={str(settings.NPM_AUDIT).lower()}\n"
            f"store-dir={store_path}\n"
        )

        with open(npmrc, "w", encoding="utf-8") as f:
            f.write(content)

    async def scaffold(self, template_dir: str) -> None:
        logger.info("Bootstrapping sandbox workspace for %s", self.project_id)
        shutil.copytree(template_dir, self.workspace_dir, dirs_exist_ok=True)

        self._stamp_vite_config(template_dir)
        self._configure_preview_paths()
        self.configure_npmrc()

        async for line in self.exec("pnpm install 2>&1"):
            logger.info("[scaffold] %s", line.rstrip())

    def _npm_package_declared(self, package_name: str) -> bool:
        pkg_path = os.path.join(self.workspace_dir, "package.json")
        if not os.path.isfile(pkg_path):
            return False
        with open(pkg_path, encoding="utf-8") as handle:
            pkg = json.load(handle)
        return package_name in pkg.get("dependencies", {})

    def _npm_package_available(self, package_name: str) -> bool:
        module_path = os.path.join(self.workspace_dir, "node_modules", *package_name.split("/"))
        return self._npm_package_declared(package_name) and os.path.exists(module_path)

    async def enable_optional_packages(self, package_names: list[str]) -> None:
        """Install and verify all already-whitelisted optional packages."""
        unique_names = list(dict.fromkeys(package_names))
        missing = [name for name in unique_names if not self._npm_package_available(name)]
        if missing:
            command = "pnpm add " + " ".join(shlex.quote(name) for name in missing) + " 2>&1"
            async for line in self.exec(command):
                logger.info("[optional-packages] %s", line.rstrip())

        unavailable = [name for name in unique_names if not self._npm_package_available(name)]
        if unavailable:
            raise RuntimeError(f"Optional package installation failed: {', '.join(unavailable)}")

    def _stamp_vite_config(self, template_dir: str) -> None:
        template_path = os.path.join(template_dir, "vite.config.ts")
        with open(template_path, encoding="utf-8") as f:
            content = f.read()
        content = (
            content.replace("{{PROJECT_ID}}", self.project_id)
            .replace("{{AUTH_PROVIDER_URL}}", settings.SANDBOX_AUTH_PROVIDER_URL)
            .replace("{{AUTH_STORAGE_KEY}}", settings.SANDBOX_AUTH_STORAGE_KEY)
            .replace("{{AUTH_USE_IFRAME}}", str(settings.SANDBOX_AUTH_USE_IFRAME).lower())
            .replace("{{AUTH_POST_MESSAGE_TARGET}}", settings.SANDBOX_AUTH_POST_MESSAGE_TARGET)
        )
        dest_path = os.path.join(self.workspace_dir, "vite.config.ts")
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content)

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
        env.update(
            sandbox_path_env(
                public_base=preview_base_path(self.project_id),
                api_base_url=settings.EXPORT_API_BASE_URL,
            )
        )
        env["FORCE_COLOR"] = "1"

        cmd = f"pnpm dev --port {self.port} --strictPort --host 0.0.0.0"
        await self._spawn_background("dev-server", cmd, env)
        logger.info("Dev server started for %s on port %d", self.project_id, self.port)

    def _configure_preview_paths(self) -> None:
        env_path = os.path.join(self.workspace_dir, ".env.local")
        env_vars = sandbox_path_env(
            public_base=preview_base_path(self.project_id),
            api_base_url=settings.EXPORT_API_BASE_URL,
        )
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(f"{key}={value}" for key, value in env_vars.items()) + "\n")

    async def stop_dev_server(self) -> None:
        await self.stop_background_process("dev-server")

    def is_dev_server_running(self) -> bool:
        return self.is_background_process_running("dev-server")
