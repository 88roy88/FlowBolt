from enum import StrEnum
from unittest.mock import patch
from urllib.parse import quote

import pytest

from flow44 import feature_flags
from flow44.api.admin import require_admin
from flow44.feature_flags import FlagSpec
from flow44.main import app

GROUP_DN = "CN=Beta Testers,OU=Groups,DC=corp"


class _Flag(StrEnum):
    beta = "beta"
    on_by_default = "on_by_default"


@pytest.fixture(autouse=True)
def _registry():
    with patch.dict(feature_flags.FLAGS, {_Flag.beta: FlagSpec("Beta feature")}, clear=True):
        yield


@pytest.fixture
def as_admin():
    """test-user is not in SYSTEM_ADMIN_IDS, so the admin gate must be overridden."""
    app.dependency_overrides[require_admin] = lambda: "test-user"
    yield
    app.dependency_overrides.pop(require_admin, None)


async def _features(client) -> list[str]:
    response = await client.get("/api/config")
    assert response.status_code == 200
    return response.json()["features"]


async def test_non_admin_is_forbidden(async_client):
    response = await async_client.get("/api/admin/flags")
    assert response.status_code == 403


@pytest.mark.usefixtures("as_admin")
class TestAdminFlags:
    async def test_lists_registered_flags_off_by_default(self, async_client, test_db):
        response = await async_client.get("/api/admin/flags")

        assert response.status_code == 200
        assert response.json() == [
            {
                "key": "beta",
                "description": "Beta feature",
                "enabled_for_all": False,
                "enabled_for_admins": False,
                "targets": [],
            }
        ]

    async def test_unknown_flag_is_404(self, async_client, test_db):
        assert (await async_client.put("/api/admin/flags/nope", json={"enabled_for_all": True})).status_code == 404
        response = await async_client.post(
            "/api/admin/flags/nope/targets", json={"target_type": "user", "target_id": "alice"}
        )
        assert response.status_code == 404

    async def test_enabled_for_all_round_trip(self, async_client, test_db):
        assert await _features(async_client) == []

        response = await async_client.put("/api/admin/flags/beta", json={"enabled_for_all": True})
        assert response.status_code == 204
        assert await _features(async_client) == ["beta"]

        # A partial update leaves the other switch alone.
        await async_client.put("/api/admin/flags/beta", json={"enabled_for_admins": True})
        flag = (await async_client.get("/api/admin/flags")).json()[0]
        assert flag["enabled_for_all"] is True
        assert flag["enabled_for_admins"] is True

    async def test_add_and_remove_user_target(self, async_client, test_db):
        response = await async_client.post(
            "/api/admin/flags/beta/targets",
            json={"target_type": "user", "target_id": "Test-User", "display_name": "Test User"},
        )
        assert response.status_code == 201
        assert response.json()["target_id"] == "test-user"
        assert await _features(async_client) == ["beta"]

        response = await async_client.delete("/api/admin/flags/beta/targets/user/Test-User")
        assert response.status_code == 204
        assert await _features(async_client) == []
        assert (await async_client.get("/api/admin/flags")).json()[0]["targets"] == []

    async def test_multiple_targets_on_one_flag(self, async_client, test_db):
        for target in [
            {"target_type": "user", "target_id": "alice"},
            {"target_type": "user", "target_id": "bob"},
            {"target_type": "group", "target_id": GROUP_DN, "display_name": "Beta Testers"},
        ]:
            assert (await async_client.post("/api/admin/flags/beta/targets", json=target)).status_code == 201

        targets = (await async_client.get("/api/admin/flags")).json()[0]["targets"]
        assert [(t["target_type"], t["target_id"]) for t in targets] == [
            ("user", "alice"),
            ("user", "bob"),
            ("group", GROUP_DN),
        ]

        # The DN has commas and '='; it round-trips URL-encoded in the path.
        response = await async_client.delete(f"/api/admin/flags/beta/targets/group/{quote(GROUP_DN, safe='')}")
        assert response.status_code == 204

    async def test_duplicate_target_is_409(self, async_client, test_db):
        body = {"target_type": "user", "target_id": "alice"}
        assert (await async_client.post("/api/admin/flags/beta/targets", json=body)).status_code == 201
        assert (await async_client.post("/api/admin/flags/beta/targets", json=body)).status_code == 409

    async def test_remove_missing_target_is_404(self, async_client, test_db):
        response = await async_client.delete("/api/admin/flags/beta/targets/user/alice")
        assert response.status_code == 404


@pytest.mark.usefixtures("as_admin")
class TestFlagCodeDefaults:
    @pytest.fixture(autouse=True)
    def _default_on(self, monkeypatch):
        monkeypatch.setitem(feature_flags.FLAGS, _Flag.on_by_default, FlagSpec("On", default_for_all=True))

    async def _flag(self, client) -> dict:
        flags = (await client.get("/api/admin/flags")).json()
        return next(f for f in flags if f["key"] == "on_by_default")

    async def test_unconfigured_flag_shows_and_serves_its_default(self, async_client, test_db):
        assert (await self._flag(async_client))["enabled_for_all"] is True
        assert await _features(async_client) == ["on_by_default"]

    async def test_first_change_keeps_the_other_default(self, async_client, test_db):
        await async_client.put("/api/admin/flags/on_by_default", json={"enabled_for_admins": True})
        flag = await self._flag(async_client)
        assert flag["enabled_for_all"] is True
        assert flag["enabled_for_admins"] is True

    async def test_first_target_keeps_the_default(self, async_client, test_db):
        await async_client.post(
            "/api/admin/flags/on_by_default/targets", json={"target_type": "user", "target_id": "alice"}
        )
        assert (await self._flag(async_client))["enabled_for_all"] is True

    async def test_turning_off_overrides_the_default(self, async_client, test_db):
        await async_client.put("/api/admin/flags/on_by_default", json={"enabled_for_all": False})
        assert (await self._flag(async_client))["enabled_for_all"] is False
        assert await _features(async_client) == []
