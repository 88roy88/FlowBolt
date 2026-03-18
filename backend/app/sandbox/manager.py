"""Sandbox lifecycle manager (singleton)."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal
from dataclasses import dataclass
from typing import IO

from app.config import settings
from app.sandbox.nsjail import build_nsjail_command

logger = logging.getLogger(__name__)


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill a subprocess and its entire process group.

    On macOS (no nsjail) subprocesses spawned with ``start_new_session=True``
    get their own process group.  ``os.killpg`` sends SIGTERM to the whole
    group so child processes (pnpm, node, vite, esbuild) don't survive as
    orphans.
    """
    if proc.returncode is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        await proc.wait()
    except ProcessLookupError:
        pass


def patch_tsconfig(workspace_dir: str) -> None:
    """Disable verbatimModuleSyntax in tsconfig.app.json and tsconfig.node.json."""
    import json as _json
    import re

    def strip_json_comments(text: str) -> str:
        """Strip comments and trailing commas from JSON to make it parseable.

        This handles JSONC (JSON with Comments) format commonly used in tsconfig.json files.
        Properly handles strings to avoid removing // or /* inside string values.
        """
        result = []
        in_string = False
        escape_next = False
        i = 0

        while i < len(text):
            char = text[i]

            # Handle string state
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue

            if char == '\\' and in_string:
                escape_next = True
                result.append(char)
                i += 1
                continue

            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue

            # Skip comments only when not in a string
            if not in_string:
                # Check for single-line comment
                if i + 1 < len(text) and text[i:i+2] == '//':
                    # Skip until end of line
                    while i < len(text) and text[i] != '\n':
                        i += 1
                    continue

                # Check for multi-line comment
                if i + 1 < len(text) and text[i:i+2] == '/*':
                    # Skip until */
                    i += 2
                    while i + 1 < len(text):
                        if text[i:i+2] == '*/':
                            i += 2
                            break
                        i += 1
                    continue

            result.append(char)
            i += 1

        clean_text = ''.join(result)
        # Remove trailing commas before closing braces/brackets
        clean_text = re.sub(r',(\s*[}\]])', r'\1', clean_text)
        return clean_text

    for name in ("tsconfig.app.json", "tsconfig.node.json"):
        path = os.path.join(workspace_dir, name)
        if not os.path.isfile(path):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Strip comments and trailing commas before parsing
            clean_content = strip_json_comments(content)
            data = _json.loads(clean_content)
        except _json.JSONDecodeError as e:
            logger.warning("Failed to parse %s: %s", path, e)
            continue
        except Exception as e:
            logger.warning("Failed to read %s: %s", path, e)
            continue

        opts = data.get("compilerOptions", {})
        if opts.pop("verbatimModuleSyntax", None) is not None:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, indent=2)
                    f.write("\n")
            except Exception as e:
                logger.warning("Failed to write %s: %s", path, e)


def write_vite_config(session_id: str, workspace_dir: str | None = None) -> None:
    """Write a vite.config.ts with the correct ``base`` for the preview proxy.

    If *workspace_dir* is not given, it is looked up from the sandbox registry.
    """
    if workspace_dir is None:
        info = sandbox_manager.get_sandbox(session_id)
        if info is None:
            return
        workspace_dir = info.workspace_dir

    config = (
        "import { defineConfig } from 'vite'\n"
        "import react from '@vitejs/plugin-react'\n"
        "\n"
        "// https://vitejs.dev/config/\n"
        "export default defineConfig({\n"
        "  plugins: [react()],\n"
        f"  base: '/api/preview/{session_id}/proxy/',\n"
        "})\n"
    )
    path = os.path.join(workspace_dir, "vite.config.ts")
    with open(path, "w", encoding="utf-8") as f:
        f.write(config)


def inject_error_reporter(workspace_dir: str) -> None:
    """Inject a runtime error reporter script into index.html.

    The script catches uncaught errors and unhandled rejections, then posts
    them to the parent window via postMessage so the builder UI can display
    them.
    """
    index_path = os.path.join(workspace_dir, "index.html")
    if not os.path.isfile(index_path):
        return

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Don't inject twice
    if "__ERROR_REPORTER__" in html:
        return

    script = (
        '<script id="__ERROR_REPORTER__">\n'
        "(function(){\n"
        "  function report(err){\n"
        "    if(!window.parent||window.parent===window)return;\n"
        "    window.parent.postMessage({\n"
        "      type:'runtime-error',\n"
        "      message:String(err.message||err),\n"
        "      file:err.filename||err.fileName||'',\n"
        "      line:err.lineno||err.lineNumber||0,\n"
        "      column:err.colno||err.columnNumber||0,\n"
        "      stack:err.error?err.error.stack||'':''\n"
        "    },'*');\n"
        "  }\n"
        "  window.addEventListener('error',function(e){report(e)});\n"
        "  window.addEventListener('unhandledrejection',function(e){\n"
        "    var r=e.reason||{};\n"
        "    report({message:r.message||String(r),stack:r.stack||''});\n"
        "  });\n"
        "})()\n"
        "</script>\n"
    )

    html = html.replace("</head>", script + "</head>", 1)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)


def write_tailwind_config(workspace_dir: str) -> None:
    """Write tailwind.config.js for Tailwind CSS v3."""
    config = (
        "/** @type {import('tailwindcss').Config} */\n"
        "export default {\n"
        "  content: [\n"
        '    "./index.html",\n'
        '    "./src/**/*.{js,ts,jsx,tsx}",\n'
        "  ],\n"
        "  theme: {\n"
        "    extend: {},\n"
        "  },\n"
        "  plugins: [],\n"
        "}\n"
    )
    path = os.path.join(workspace_dir, "tailwind.config.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(config)


def write_postcss_config(workspace_dir: str) -> None:
    """Write postcss.config.js for Tailwind CSS."""
    config = (
        "export default {\n"
        "  plugins: {\n"
        "    tailwindcss: {},\n"
        "    autoprefixer: {},\n"
        "  },\n"
        "}\n"
    )
    path = os.path.join(workspace_dir, "postcss.config.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(config)


def inject_tailwind_directives(workspace_dir: str) -> None:
    """Add @tailwind directives to src/index.css."""
    css_path = os.path.join(workspace_dir, "src", "index.css")
    if not os.path.isfile(css_path):
        return

    with open(css_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Don't inject if already present
    if "@tailwind" in content:
        return

    # Prepend Tailwind directives
    tailwind_directives = (
        "@tailwind base;\n"
        "@tailwind components;\n"
        "@tailwind utilities;\n\n"
    )
    content = tailwind_directives + content

    with open(css_path, "w", encoding="utf-8") as f:
        f.write(content)


@dataclass
class SandboxInfo:
    """Runtime information for a single sandbox."""

    session_id: str
    workspace_dir: str
    port: int
    process: asyncio.subprocess.Process | None = None
    dev_process: asyncio.subprocess.Process | None = None
    _dev_log_file: IO[bytes] | None = None  # file handle for .dev-server.log


class SandboxManager:
    """Manages sandbox creation, lookup, and teardown.

    Maintains a pool of available ports and a registry of active sandboxes.
    Designed as a singleton — import :pydata:`sandbox_manager` from this module.
    """

    def __init__(self) -> None:
        self._sandboxes: dict[str, SandboxInfo] = {}
        self._available_ports: set[int] = set(
            range(settings.SANDBOX_PORT_RANGE_START, settings.SANDBOX_PORT_RANGE_END + 1)
        )
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_sandbox(self, session_id: str) -> SandboxInfo:
        """Create a workspace directory, allocate a port, and start a long-lived
        bash shell process inside nsjail (or a plain subprocess in fallback mode).
        """
        async with self._lock:
            if session_id in self._sandboxes:
                return self._sandboxes[session_id]

            if not self._available_ports:
                raise RuntimeError("No available ports in the sandbox pool")

            port = self._available_ports.pop()

        workspace_dir = os.path.join(settings.WORKSPACE_BASE_DIR, session_id)
        os.makedirs(workspace_dir, exist_ok=True)

        cmd = build_nsjail_command(session_id, workspace_dir, port, command=None)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,  # own process group so killpg works
        )

        info = SandboxInfo(
            session_id=session_id,
            workspace_dir=workspace_dir,
            port=port,
            process=process,
        )

        self._sandboxes[session_id] = info
        return info

    async def destroy_sandbox(self, session_id: str, *, delete_workspace: bool = True) -> None:
        """Kill the sandbox process, free the port, and optionally remove the workspace.

        Parameters
        ----------
        delete_workspace:
            When *False* the workspace directory is preserved on disk.  This is
            used during hot-reload / graceful shutdown so files aren't lost.
        """
        async with self._lock:
            info = self._sandboxes.pop(session_id, None)

        if info is None:
            return

        # Terminate the dev server and close its log file
        if info.dev_process is not None:
            await _kill_process_tree(info.dev_process)
        if info._dev_log_file is not None:
            try:
                info._dev_log_file.close()
            except Exception:
                pass

        # Terminate the long-lived shell process
        if info.process is not None:
            await _kill_process_tree(info.process)

        # Return port to pool
        async with self._lock:
            self._available_ports.add(info.port)

        # Clean up workspace only when explicitly requested
        if delete_workspace and os.path.isdir(info.workspace_dir):
            shutil.rmtree(info.workspace_dir, ignore_errors=True)

    async def start_dev_server(self, session_id: str) -> None:
        """Start `pnpm dev` on the sandbox's allocated port as a background process.

        Stdout/stderr are redirected to ``.dev-server.log`` inside the workspace
        so the dev server never blocks on a full pipe buffer.  Users can view
        the log via ``tail -f .dev-server.log`` in the terminal.
        """
        info = self._sandboxes.get(session_id)
        if info is None:
            logger.warning("Cannot start dev server: no sandbox for %s", session_id)
            return

        # Kill existing dev server if running
        if info.dev_process is not None:
            await _kill_process_tree(info.dev_process)

        log_path = os.path.join(info.workspace_dir, ".dev-server.log")

        from app.sandbox.nsjail import _nsjail_available

        if not _nsjail_available():
            # macOS dev: run pnpm directly with FORCE_COLOR for ANSI output.
            dev_cmd = f"pnpm dev --port {info.port} --host 0.0.0.0"
            log_file = open(log_path, "wb")  # noqa: SIM115

            env = os.environ.copy()
            env["FORCE_COLOR"] = "1"

            info.dev_process = await asyncio.create_subprocess_exec(
                "/bin/bash", "-c", f"cd {info.workspace_dir} && {dev_cmd}",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            info._dev_log_file = log_file
        else:
            log_file = open(log_path, "wb")  # noqa: SIM115

            cmd = build_nsjail_command(
                session_id,
                info.workspace_dir,
                info.port,
                command=f"pnpm dev --port {info.port} --host 0.0.0.0",
            )

            env = os.environ.copy()
            env["FORCE_COLOR"] = "1"

            info.dev_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            info._dev_log_file = log_file
        logger.info(
            "Dev server started for session %s on port %d (pid %s)",
            session_id, info.port, info.dev_process.pid,
        )

    def get_sandbox(self, session_id: str) -> SandboxInfo | None:
        """Look up sandbox info by session id (non-blocking)."""
        return self._sandboxes.get(session_id)

    @staticmethod
    def _kill_stale_dev_servers() -> None:
        """Kill any leftover pnpm/vite processes from previous runs.

        This handles the case where uvicorn --reload killed the Python
        process but the child node processes survived as orphans.
        """
        import subprocess as _sp

        port_start = settings.SANDBOX_PORT_RANGE_START
        port_end = settings.SANDBOX_PORT_RANGE_END
        try:
            result = _sp.run(
                ["pgrep", "-f", "pnpm dev --port"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return
            for pid_str in result.stdout.strip().splitlines():
                pid = int(pid_str.strip())
                # Read cmdline to check if port is in our range
                try:
                    cmdline = _sp.run(
                        ["ps", "-p", str(pid), "-o", "args="],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.strip()
                except Exception:
                    continue
                # Extract port from "pnpm dev --port NNNN"
                for part in cmdline.split():
                    try:
                        port = int(part)
                        if port_start <= port <= port_end:
                            try:
                                os.killpg(os.getpgid(pid), signal.SIGTERM)
                            except (ProcessLookupError, PermissionError, OSError):
                                try:
                                    os.kill(pid, signal.SIGTERM)
                                except (ProcessLookupError, PermissionError):
                                    pass
                            logger.info("Killed stale dev server pid %d (port %d)", pid, port)
                            break
                    except ValueError:
                        continue
        except FileNotFoundError:
            pass  # pgrep not available
        except Exception:
            logger.debug("Failed to clean stale dev servers", exc_info=True)

    async def restore_existing_workspaces(self) -> None:
        """Re-register sandboxes for workspace directories that still have a
        matching project in the database.

        Called on startup so that after a uvicorn reload the file APIs still work
        for sessions whose workspace was preserved.  Orphan directories (project
        deleted but workspace left on disk) are cleaned up automatically.
        """
        # Kill any orphan dev servers left from previous runs
        self._kill_stale_dev_servers()

        base = settings.WORKSPACE_BASE_DIR
        if not os.path.isdir(base):
            return

        # Query the DB for all live session IDs
        from app.models.project import list_projects

        live_projects = await list_projects()
        live_session_ids = {p.session_id for p in live_projects}

        for name in os.listdir(base):
            workspace_dir = os.path.join(base, name)
            if not os.path.isdir(workspace_dir):
                continue
            if name in self._sandboxes:
                continue

            # Remove orphan workspaces that have no matching project in the DB
            if name not in live_session_ids:
                logger.info("Removing orphan workspace %s (no matching project in DB)", name)
                shutil.rmtree(workspace_dir, ignore_errors=True)
                continue

            async with self._lock:
                if not self._available_ports:
                    logger.warning("No ports left to restore sandbox %s", name)
                    continue
                port = self._available_ports.pop()

            info = SandboxInfo(
                session_id=name,
                workspace_dir=workspace_dir,
                port=port,
                process=None,  # no live process — commands will spawn one-shot
            )
            self._sandboxes[name] = info
            logger.info("Restored sandbox for session %s (port %d)", name, port)

        # Patch configs, inject error reporter, ensure Tailwind configs, and restart dev servers
        for name, info in self._sandboxes.items():
            if os.path.isfile(os.path.join(info.workspace_dir, "package.json")):
                write_vite_config(name, info.workspace_dir)
                inject_error_reporter(info.workspace_dir)
                # Ensure Tailwind configs exist (idempotent)
                write_tailwind_config(info.workspace_dir)
                write_postcss_config(info.workspace_dir)
                inject_tailwind_directives(info.workspace_dir)
                asyncio.create_task(self.start_dev_server(name))

    async def destroy_all(self, *, delete_workspaces: bool = False) -> None:
        """Tear down every active sandbox.  Used during application shutdown.

        By default workspaces are preserved so hot-reloads don't lose user files.
        Pass ``delete_workspaces=True`` for a full cleanup.
        """
        session_ids = list(self._sandboxes.keys())
        for sid in session_ids:
            await self.destroy_sandbox(sid, delete_workspace=delete_workspaces)


# Module-level singleton
sandbox_manager = SandboxManager()
