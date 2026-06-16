from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from flow44.api.projects import delete_existing_project
from flow44.db.project import Project


@pytest.mark.asyncio
async def test_delete_existing_project_schedules_s3_cleanup():
    project = Project(id="proj-123", user_id="user-1", name="App")
    background_tasks = MagicMock(spec=BackgroundTasks)

    with (
        patch("flow44.api.projects.idle_reaper.remove") as mock_idle_remove,
        patch("flow44.api.projects.delete_project", new=AsyncMock()) as mock_delete_project,
        patch("flow44.api.projects.delete_published_object") as mock_delete_published_object,
    ):
        await delete_existing_project(project, background_tasks, _perms=set())

    mock_idle_remove.assert_called_once_with("proj-123")
    mock_delete_project.assert_awaited_once_with("proj-123")
    background_tasks.add_task.assert_any_call(mock_delete_published_object, "proj-123")
