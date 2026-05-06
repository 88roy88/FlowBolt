import pytest
from fastapi import HTTPException

from flow44.api.auth import get_project
from flow44.db.project import create_project


@pytest.mark.asyncio
async def test_project_user_isolation(test_db):
    # Create project for User A
    project_a = await create_project(name="Project A", user_id="user_a")

    # User A should be able to get their project
    retrieved_a = await get_project(project_id=project_a.id, user_id="user_a")
    assert retrieved_a.id == project_a.id
    assert retrieved_a.user_id == "user_a"

    # User B should NOT be able to get User A's project (should raise 404)
    with pytest.raises(HTTPException) as exc:
        await get_project(project_id=project_a.id, user_id="user_b")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found"

@pytest.mark.asyncio
async def test_list_projects_isolation(test_db):
    await create_project(name="A1", user_id="user_a")
    await create_project(name="A2", user_id="user_a")
    await create_project(name="B1", user_id="user_b")

    from flow44.db.project import list_projects

    projects_a = await list_projects(user_id="user_a")
    assert len(projects_a) == 2
    assert all(p.user_id == "user_a" for p in projects_a)

    projects_b = await list_projects(user_id="user_b")
    assert len(projects_b) == 1
    assert projects_b[0].user_id == "user_b"

    # System level (None) should see all
    all_projects = await list_projects(user_id=None)
    assert len(all_projects) == 3
