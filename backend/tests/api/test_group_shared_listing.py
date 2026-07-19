"""The project list must surface projects shared with the user via a directory
group, not only owned and directly-shared ones. Covers the DB helper, the
endpoint, and role precedence when a project reaches the user by several paths.
"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from flow44.auth.permissions import Role
from flow44.db.project import create_project
from flow44.db.project_member import add_member
from flow44.db.project_member_group import add_group, list_group_shared_projects
from flow44.main import app

client = TestClient(app)

GROUP_A = "c330021a-a75a-09a8-1725-d8e0af4fc83e"
GROUP_B = "d441132b-b86b-1ab9-2836-e9f1bf5fd94f"


class TestListGroupSharedProjectsDB:
    async def test_returns_matching_group_grants(self, test_db):
        project = await create_project(name="Shared", user_id="owner")
        await add_group(project.id, GROUP_A, "Cloud Leads", Role.editor, "owner")

        rows = await list_group_shared_projects({GROUP_A})
        assert [(p.id, role) for p, role in rows] == [(project.id, Role.editor)]

    async def test_ignores_non_member_groups(self, test_db):
        project = await create_project(name="Shared", user_id="owner")
        await add_group(project.id, GROUP_A, "Cloud Leads", Role.editor, "owner")

        assert await list_group_shared_projects({GROUP_B}) == []

    async def test_empty_group_set_short_circuits(self, test_db):
        assert await list_group_shared_projects(set()) == []


class TestGroupSharedListingEndpoint:
    async def test_group_shared_project_appears_in_list(self, test_db):
        project = await create_project(name="Team Project", user_id="owner")
        await add_group(project.id, GROUP_A, "Cloud Leads", Role.editor, "owner")

        with patch(
            "flow44.api.projects.adapi_client.get_user_group_ids",
            new=AsyncMock(return_value={GROUP_A}),
        ):
            resp = client.get("/api/projects")

        assert resp.status_code == 200
        by_id = {p["id"]: p for p in resp.json()}
        assert project.id in by_id
        assert by_id[project.id]["role"] == Role.editor.value

    async def test_non_matching_group_omits_group_shared_projects(self, test_db):
        # The user belongs to GROUP_B but the project is shared with GROUP_A, so it
        # must not appear. Exercises the group intersection filter itself, not the
        # empty-set short-circuit (covered by TestListGroupSharedProjectsDB).
        project = await create_project(name="Team Project", user_id="owner")
        await add_group(project.id, GROUP_A, "Cloud Leads", Role.editor, "owner")

        with patch(
            "flow44.api.projects.adapi_client.get_user_group_ids",
            new=AsyncMock(return_value={GROUP_B}),
        ):
            resp = client.get("/api/projects")

        assert resp.status_code == 200
        assert project.id not in {p["id"] for p in resp.json()}

    async def test_direct_and_group_share_collapse_to_highest_role(self, test_db):
        # test-user is a direct editor and also a maintainer via a group grant.
        project = await create_project(name="Team Project", user_id="owner")
        await add_member(project.id, "test-user", Role.editor, "owner")
        await add_group(project.id, GROUP_A, "Cloud Leads", Role.maintainer, "owner")

        with patch(
            "flow44.api.projects.adapi_client.get_user_group_ids",
            new=AsyncMock(return_value={GROUP_A}),
        ):
            resp = client.get("/api/projects")

        assert resp.status_code == 200
        entries = [p for p in resp.json() if p["id"] == project.id]
        assert len(entries) == 1  # deduped, not listed twice
        assert entries[0]["role"] == Role.maintainer.value
