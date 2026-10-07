"""Tests for the paginated, searchable GET /api/projects listing."""

import pytest
from httpx import ASGITransport, AsyncClient

from flow44.auth.permissions import Role
from flow44.config import settings
from flow44.db.project import create_project
from flow44.db.project_member import add_member
from flow44.main import app


@pytest.fixture
async def client():
    # In-loop client: test_db binds sessions to a connection on the test's event loop,
    # which TestClient (running the app on its own loop) can't use.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def as_admin(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_ADMIN_IDS", ["test-user"])


async def _list(client: AsyncClient, **params: str | int) -> dict:
    response = await client.get("/api/projects", params=params)
    assert response.status_code == 200, response.text
    return response.json()


class TestListProjects:
    async def test_includes_owned_and_shared_with_roles(self, test_db, client):
        owned = await create_project("Mine", user_id="test-user")
        shared = await create_project("Theirs", user_id="someone-else")
        await create_project("Hidden", user_id="someone-else")
        await add_member(shared.id, "test-user", Role.editor, invited_by="someone-else")

        body = await _list(client)

        assert {(p["id"], p["role"]) for p in body["projects"]} == {(owned.id, "owner"), (shared.id, "editor")}
        assert body["next_cursor"] is None

    async def test_pages_through_all_projects_without_overlap(self, test_db, client):
        created = [await create_project(f"P{i}", user_id="test-user") for i in range(5)]

        seen: list[str] = []
        cursor = None
        while True:
            body = await _list(client, limit=2, **({"cursor": cursor} if cursor else {}))
            assert len(body["projects"]) <= 2
            seen += [p["id"] for p in body["projects"]]
            cursor = body["next_cursor"]
            if cursor is None:
                break

        assert seen == [p.id for p in reversed(created)]

    async def test_search_filters_by_name_case_insensitively(self, test_db, client):
        match = await create_project("Sales Dashboard", user_id="test-user")
        await create_project("Inventory", user_id="test-user")

        body = await _list(client, q="dashBOARD")

        assert [p["id"] for p in body["projects"]] == [match.id]

    async def test_search_treats_like_wildcards_literally(self, test_db, client):
        literal = await create_project("100%_done", user_id="test-user")
        await create_project("100 done", user_id="test-user")

        assert [p["id"] for p in (await _list(client, q="%_"))["projects"]] == [literal.id]

    async def test_search_paginates(self, test_db, client):
        matches = [await create_project(f"report {i}", user_id="test-user") for i in range(3)]
        await create_project("other", user_id="test-user")

        first = await _list(client, q="report", limit=2)
        second = await _list(client, q="report", limit=2, cursor=first["next_cursor"])

        assert [p["id"] for p in first["projects"] + second["projects"]] == [p.id for p in reversed(matches)]
        assert second["next_cursor"] is None

    async def test_admin_sees_all_projects_as_admin_even_when_a_member(self, test_db, client, as_admin):
        owned = await create_project("Mine", user_id="test-user")
        unrelated = await create_project("Unrelated", user_id="someone-else")
        member_of = await create_project("Shared", user_id="someone-else")
        await add_member(member_of.id, "test-user", Role.viewer, invited_by="someone-else")

        roles = {p["id"]: p["role"] for p in (await _list(client))["projects"]}

        assert roles == {owned.id: "owner", unrelated.id: "admin", member_of.id: "admin"}

    async def test_rejects_malformed_cursor(self, client):
        assert (await client.get("/api/projects", params={"cursor": "not-a-cursor"})).status_code == 400


class TestGetProject:
    async def test_returns_project_with_member_role(self, test_db, client):
        project = await create_project("Shared", user_id="someone-else")
        await add_member(project.id, "test-user", Role.viewer, invited_by="someone-else")

        response = await client.get(f"/api/projects/{project.id}")

        assert response.status_code == 200
        assert response.json()["role"] == "viewer"

    async def test_hides_inaccessible_project(self, test_db, client):
        project = await create_project("Private", user_id="someone-else")

        assert (await client.get(f"/api/projects/{project.id}")).status_code == 404

    async def test_admin_member_gets_admin_role(self, test_db, client, as_admin):
        project = await create_project("Shared", user_id="someone-else")
        await add_member(project.id, "test-user", Role.viewer, invited_by="someone-else")

        assert (await client.get(f"/api/projects/{project.id}")).json()["role"] == "admin"
