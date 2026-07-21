from unittest.mock import patch

import httpx
import pytest

from flow44.integrations.adapi.client import AdapiClient, AdapiError


def _resp(status_code: int, json_data: object) -> httpx.Response:
    request = httpx.Request("GET", "http://adapi.local/api/users")
    return httpx.Response(status_code, json=json_data, request=request)


class TestSearchUsers:
    @pytest.mark.asyncio
    async def test_returns_typed_users_and_ignores_unknown_fields(self):
        payload = [
            {
                "cn": "djenkins",
                "displayName": "Dana Jenkins",
                "distinguishedName": "CN=djenkins,OU=Staff,DC=corp",
                "mail": "dj@corp.local",
                "sAMAccountName": "djenkins",
                "whenCreated": "20240101",  # extra field must be ignored, not rejected
            }
        ]
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(200, payload)) as mock_get:
            users = await client.search_users("dje")

        # The term is wildcard-wrapped and matched against account name, display name
        # and mail. The query rides in the URL, pre-encoded: the space inside
        # customFilter must be %20 (not +, which ADAPI rejects).
        requested_url = mock_get.call_args.args[0]
        assert requested_url == (
            "/users?samAccountName=%2Adje%2A"
            "&customFilter=%28%7C%28displayName%3D%2Adje%2A%29%20%28mail%3D%2Adje%2A%29%29"
        )
        assert "+" not in requested_url
        assert len(users) == 1
        assert users[0].cn == "djenkins"
        assert users[0].display_name == "Dana Jenkins"

    def test_sends_client_id_header(self):
        # Explicit override wins; otherwise it falls back to the configured default.
        assert AdapiClient(base_url="http://adapi.local", client_id="acme")._headers == {"ClientId": "acme"}
        assert "ClientId" in AdapiClient(base_url="http://adapi.local")._headers

    @pytest.mark.asyncio
    async def test_empty_result_is_not_an_error(self):
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(200, [])):
            assert await client.search_users("nobody") == []

    @pytest.mark.asyncio
    async def test_http_error_raises_adapi_error(self):
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(500, {"error": "boom"})), \
             pytest.raises(AdapiError):
            await client.search_users("dje")

    @pytest.mark.asyncio
    async def test_transport_failure_raises_adapi_error(self):
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")), \
             pytest.raises(AdapiError):
            await client.search_users("dje")

    @pytest.mark.asyncio
    async def test_non_list_payload_raises_adapi_error(self):
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(200, {"unexpected": "object"})), \
             pytest.raises(AdapiError):
            await client.search_users("dje")


class TestSearchGroups:
    @pytest.mark.asyncio
    async def test_returns_typed_groups_with_description(self):
        payload = [
            {
                "cn": "Legal",
                "displayName": "Legal Team",
                "distinguishedName": "CN=Legal,OU=Groups,DC=corp",
                "description": "Legal department",
                "mail": "legal@corp.local",
                "sAMAccountName": "legal",
                "objectGUID": "82e16f20-f05e-6d5c-3589-79cd6b398160",
            }
        ]
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(200, payload)):
            groups = await client.search_groups("le")

        assert len(groups) == 1
        assert groups[0].cn == "Legal"
        assert groups[0].description == "Legal department"
        # objectGUID is surfaced as a stable directory id, alongside the DN used for grants.
        assert groups[0].object_guid == "82e16f20-f05e-6d5c-3589-79cd6b398160"


class TestGetUserGroupIds:
    @staticmethod
    def _user(sam: str, member_of: list[str]) -> dict:
        return {
            "cn": sam,
            "displayName": sam,
            "distinguishedName": f"CN={sam},OU=Users,DC=corp",
            "mail": f"{sam}@corp.local",
            "sAMAccountName": sam,
            "memberOf": member_of,
        }

    @pytest.mark.asyncio
    async def test_returns_member_of_dns_for_exact_match(self):
        dns = ["CN=Legal,OU=Groups,DC=corp", "CN=Engineering,OU=Groups,DC=corp"]
        # A substring search can return several users; only the exact mail counts.
        payload = [self._user("djenkins", dns), self._user("djenkinson", ["CN=Other,OU=Groups,DC=corp"])]
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(200, payload)):
            assert await client.get_user_group_ids("djenkins@corp.local") == set(dns)

    @pytest.mark.asyncio
    async def test_match_is_case_insensitive(self):
        client = AdapiClient(base_url="http://adapi.local")
        # Stored mail is DJenkins@corp.local; query with a different case must still match.
        payload = [self._user("DJenkins", ["CN=Legal,OU=Groups,DC=corp"])]
        with patch("httpx.AsyncClient.get", return_value=_resp(200, payload)):
            assert await client.get_user_group_ids("djenkins@corp.local") == {"CN=Legal,OU=Groups,DC=corp"}

    @pytest.mark.asyncio
    async def test_no_exact_match_returns_empty_set(self):
        client = AdapiClient(base_url="http://adapi.local")
        # A substring hit that is not the requested account must not leak its groups.
        payload = [self._user("djenkinson", ["CN=Legal,OU=Groups,DC=corp"])]
        with patch("httpx.AsyncClient.get", return_value=_resp(200, payload)):
            assert await client.get_user_group_ids("djenkins@corp.local") == set()

    @pytest.mark.asyncio
    async def test_user_without_groups_returns_empty_set(self):
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", return_value=_resp(200, [self._user("djenkins", [])])):
            assert await client.get_user_group_ids("djenkins@corp.local") == set()

    @pytest.mark.asyncio
    async def test_adapi_failure_soft_fails_to_empty_set(self):
        client = AdapiClient(base_url="http://adapi.local")
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("refused")):
            assert await client.get_user_group_ids("djenkins") == set()
