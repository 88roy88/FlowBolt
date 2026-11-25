import asyncio
import os

from flow44.sandbox.base import workspace_path
from flow44.sandbox.manager import sandbox_manager


async def configure_project_npmrc(project_id: str) -> str:
    workspace_dir = workspace_path(project_id)
    if not await asyncio.to_thread(os.path.isfile, os.path.join(workspace_dir, "package.json")):
        return "workspace not present on this pod or not scaffolded, skipped"

    was_active = sandbox_manager.has_active_sandbox(project_id)
    sandbox = await sandbox_manager.get_sandbox(project_id)
    try:
        sandbox.configure_npmrc()
    finally:
        if not was_active:
            await sandbox_manager.suspend_sandbox(project_id)
    return "configured"
