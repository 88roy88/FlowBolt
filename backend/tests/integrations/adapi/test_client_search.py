"""Tests for AdapiClient search.

The key behaviour under test is the error-vs-empty distinction: unlike group
resolution (which soft-fails to an empty set), search raises ``AdapiError`` on
failure so the UI can say "ADAPI unavailable" instead of "no matches".
"""

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

        # The term is wildcard-wrapped and matched against account name, display name and mail.
        assert mock_get.call_args.kwargs["params"] == {
            "samAccountName": "*dje*",
            "customFilter": "(|(displayName=*dje*) (mail=*dje*))",
        }
        assert len(users) == 1
        assert users[0].cn == "djenkins"
        assert users[0].displayName == "Dana Jenkins"

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
        # objectGUID is surfaced so a group can be granted project access.
        assert groups[0].objectGUID == "82e16f20-f05e-6d5c-3589-79cd6b398160"
