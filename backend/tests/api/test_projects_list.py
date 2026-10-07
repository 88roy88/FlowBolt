"""Tests for the paginated, searchable GET /api/projects listing."""

from fastapi.testclient import TestClient

from flow44.auth.permissions import Role
from flow44.db.project import create_project
from flow44.db.project_member import add_member
from flow44.main import app

client = TestClient(app)


def _list(**params: str | int) -> dict:
    response = client.get("/api/projects", params=params)
    assert response.status_code == 200, response.text
    return response.json()


class TestListProjects:
    async def test_includes_owned_and_shared_with_roles(self, test_db):
        owned = await create_project("Mine", user_id="test-user")
        shared = await create_project("Theirs", user_id="someone-else")
        await create_project("Hidden", user_id="someone-else")
        await add_member(shared.id, "test-user", Role.editor, invited_by="someone-else")

        body = _list()

        assert {(p["id"], p["role"]) for p in body["projects"]} == {(owned.id, "owner"), (shared.id, "editor")}
        assert body["next_cursor"] is None

    async def test_pages_through_all_projects_without_overlap(self, test_db):
        created = [await create_project(f"P{i}", user_id="test-user") for i in range(5)]

        seen: list[str] = []
        cursor = None
        while True:
            body = _list(limit=2, **({"cursor": cursor} if cursor else {}))
            assert len(body["projects"]) <= 2
            seen += [p["id"] for p in body["projects"]]
            cursor = body["next_cursor"]
            if cursor is None:
                break

        assert seen == [p.id for p in reversed(created)]

    async def test_search_filters_by_name_case_insensitively(self, test_db):
        match = await create_project("Sales Dashboard", user_id="test-user")
        await create_project("Inventory", user_id="test-user")

        body = _list(q="dashBOARD")

        assert [p["id"] for p in body["projects"]] == [match.id]

    async def test_search_treats_like_wildcards_literally(self, test_db):
        literal = await create_project("100%_done", user_id="test-user")
        await create_project("100 done", user_id="test-user")

        assert [p["id"] for p in _list(q="%_")["projects"]] == [literal.id]

    async def test_search_paginates(self, test_db):
        matches = [await create_project(f"report {i}", user_id="test-user") for i in range(3)]
        await create_project("other", user_id="test-user")

        first = _list(q="report", limit=2)
        second = _list(q="report", limit=2, cursor=first["next_cursor"])

        assert [p["id"] for p in first["projects"] + second["projects"]] == [p.id for p in reversed(matches)]
        assert second["next_cursor"] is None

    def test_rejects_malformed_cursor(self):
        assert client.get("/api/projects", params={"cursor": "not-a-cursor"}).status_code == 400


class TestGetProject:
    async def test_returns_project_with_member_role(self, test_db):
        project = await create_project("Shared", user_id="someone-else")
        await add_member(project.id, "test-user", Role.viewer, invited_by="someone-else")

        response = client.get(f"/api/projects/{project.id}")

        assert response.status_code == 200
        assert response.json()["role"] == "viewer"

    async def test_hides_inaccessible_project(self, test_db):
        project = await create_project("Private", user_id="someone-else")

        assert client.get(f"/api/projects/{project.id}").status_code == 404
