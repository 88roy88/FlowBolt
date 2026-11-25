import asyncio
import os
import shutil

from flow44.sandbox.base import workspace_path
from flow44.sandbox.manager import sandbox_manager


async def reinstall_dependencies(project_id: str) -> str:
    workspace_dir = workspace_path(project_id)
    if not await asyncio.to_thread(os.path.isfile, os.path.join(workspace_dir, "package.json")):
        return "workspace not present on this pod or not scaffolded, skipped"

    await sandbox_manager.suspend_sandbox(project_id)
    sandbox = await sandbox_manager.get_sandbox(project_id)  # also refreshes .npmrc
    try:
        await asyncio.to_thread(shutil.rmtree, os.path.join(workspace_dir, "node_modules"), True)
        async for _ in sandbox.exec("pnpm install 2>&1"):
            pass
        if not await asyncio.to_thread(os.path.isdir, os.path.join(workspace_dir, "node_modules")):
            raise RuntimeError("pnpm install did not produce node_modules")
    finally:
        await sandbox_manager.suspend_sandbox(project_id)
    return "reinstalled"
