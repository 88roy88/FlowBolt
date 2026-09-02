
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from flow44.integrations.directory.client import DirectoryError, AdGroup, AdUser
from flow44.main import app

client = TestClient(app)


class TestDirectorySearch:
    def test_users_returns_matches_and_forwards_query(self):
        result = [AdUser(cn="djenkins", displayName="Dana Jenkins", sAMAccountName="djenkins")]
        with patch(
            "flow44.api.directory.directory_client.search_users",
            new=AsyncMock(return_value=result),
        ) as mock_search:
            resp = client.get("/api/directory/users", params={"q": "dje"})

        assert resp.status_code == 200
        assert resp.json()[0]["cn"] == "djenkins"
        mock_search.assert_awaited_once_with("dje")

    def test_groups_returns_matches(self):
        result = [AdGroup(cn="Legal", description="Legal department")]
        with patch(
            "flow44.api.directory.directory_client.search_groups",
            new=AsyncMock(return_value=result),
        ):
            resp = client.get("/api/directory/groups", params={"q": "le"})

        assert resp.status_code == 200
        assert resp.json()[0]["description"] == "Legal department"

    def test_directory_unavailable_maps_to_502(self):
        with patch(
            "flow44.api.directory.directory_client.search_users",
            new=AsyncMock(side_effect=DirectoryError("directory down")),
        ):
            resp = client.get("/api/directory/users", params={"q": "dje"})

        assert resp.status_code == 502
        assert resp.json()["detail"] == "Directory service unavailable"

    @pytest.mark.parametrize("path", ["/api/directory/users", "/api/directory/groups"])
    def test_missing_cn_defaults_to_empty_search(self, path):
        with patch(
            "flow44.api.directory.directory_client.search_users",
            new=AsyncMock(return_value=[]),
        ), patch(
            "flow44.api.directory.directory_client.search_groups",
            new=AsyncMock(return_value=[]),
        ):
            resp = client.get(path)

        assert resp.status_code == 200
        assert resp.json() == []
