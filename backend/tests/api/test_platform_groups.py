"""Tests for platform group grants: the DB layer, the admin endpoints, and the
project-creation gate honouring group membership."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from flow44.api.admin import require_admin
from flow44.api.deps import has_platform_access
from flow44.db.platform_user_group import (
    add_platform_group,
    list_platform_groups,
    platform_group_ids,
    remove_platform_group,
)
from flow44.main import app

client = TestClient(app)

GUID = "c330021a-a75a-09a8-1725-d8e0af4fc83e"


class TestPlatformGroupDB:
    async def test_add_list_remove(self, test_db):
        await add_platform_group(GUID, "Cloud Leads", "admin-user")

        groups = await list_platform_groups()
        assert [g.group_id for g in groups] == [GUID]
        assert groups[0].group_name == "Cloud Leads"
        assert await platform_group_ids() == {GUID}

        assert await remove_platform_group(GUID) is True
        assert await list_platform_groups() == []
        assert await remove_platform_group(GUID) is False


class TestPlatformAccessGate:
    async def test_no_grants_short_circuits_without_adapi_call(self, test_db):
        with patch(
            "flow44.api.deps.adapi_client.get_user_group_ids", new=AsyncMock()
        ) as mock_groups:
            assert await has_platform_access("nobody") is False
        mock_groups.assert_not_awaited()

    async def test_member_of_granted_group_gets_access(self, test_db):
        await add_platform_group(GUID, "Cloud Leads", "admin-user")
        # A non-admin, non-platform user whose ADAPI groups include the granted one.
        with patch(
            "flow44.api.deps.adapi_client.get_user_group_ids",
            new=AsyncMock(return_value={GUID}),
        ):
            assert await has_platform_access("group-member-user") is True

    async def test_non_member_is_denied(self, test_db):
        await add_platform_group(GUID, "Cloud Leads", "admin-user")
        # A user whose ADAPI groups do not include any granted group.
        with patch(
            "flow44.api.deps.adapi_client.get_user_group_ids",
            new=AsyncMock(return_value={"other-guid"}),
        ):
            assert await has_platform_access("non-member-user") is False


class TestAdminGroupEndpoints:
    def setup_method(self):
        app.dependency_overrides[require_admin] = lambda: "admin-user"

    def teardown_method(self):
        app.dependency_overrides.pop(require_admin, None)

    async def test_invite_list_revoke(self, test_db):
        resp = client.post("/api/admin/groups", json={"group_id": GUID, "group_name": "Cloud Leads"})
        assert resp.status_code == 201
        assert resp.json()["group_id"] == GUID
        assert resp.json()["invited_by"] == "admin-user"

        resp = client.get("/api/admin/groups")
        assert resp.status_code == 200
        assert resp.json()[0]["group_name"] == "Cloud Leads"

        assert client.delete(f"/api/admin/groups/{GUID}").status_code == 204
        assert client.get("/api/admin/groups").json() == []

    async def test_duplicate_grant_conflicts(self, test_db):
        assert client.post("/api/admin/groups", json={"group_id": GUID}).status_code == 201
        resp = client.post("/api/admin/groups", json={"group_id": GUID})
        assert resp.status_code == 409

    async def test_revoke_missing_is_404(self, test_db):
        assert client.delete("/api/admin/groups/does-not-exist").status_code == 404
