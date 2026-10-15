import pytest
from fastapi import HTTPException

from flow44.api.deps import get_project_with_role
from flow44.db.project import create_project


@pytest.mark.asyncio
async def test_project_user_isolation(test_db):
    # Create project for User A
    project_a = await create_project(name="Project A", user_id="user_a")

    # User A should be able to get their project
    retrieved_a = (await get_project_with_role(project_id=project_a.id, user_id="user_a")).project
    assert retrieved_a.id == project_a.id
    assert retrieved_a.user_id == "user_a"

    # User B should NOT be able to get User A's project (should raise 404)
    with pytest.raises(HTTPException) as exc:
        await get_project_with_role(project_id=project_a.id, user_id="user_b")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found"
