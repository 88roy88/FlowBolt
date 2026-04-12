"""Tests for FlapiClient — auth handling, URL construction, and high-level methods."""

from unittest.mock import AsyncMock

import pytest

from flow44.integrations.flapi_api import FlapiClient


class TestAuthHeader:
    def test_none(self) -> None:
        assert FlapiClient._build_auth_header(None) == {}

    def test_empty(self) -> None:
        assert FlapiClient._build_auth_header("") == {}

    def test_whitespace_only(self) -> None:
        assert FlapiClient._build_auth_header("   ") == {}

    def test_valid_token(self) -> None:
        assert FlapiClient._build_auth_header("my-token") == {"Authorization": "my-token"}

    def test_strips_whitespace(self) -> None:
        assert FlapiClient._build_auth_header("  admin  ") == {"Authorization": "admin"}

    def test_returns_raw_token_as_is(self) -> None:
        assert FlapiClient._build_auth_header("any-string") == {"Authorization": "any-string"}


class TestGetDisplayName:
    async def test_returns_name(self) -> None:
        client = FlapiClient("http://fake")
        client.search = AsyncMock(return_value=[{"Name": "  Sales Overview  "}])  # type: ignore[method-assign]

        result = await client.get_display_name(42, authorization="test-token")
        assert result == "Sales Overview"
        client.search.assert_called_once_with("42", authorization="test-token")

    async def test_raises_when_empty_results(self) -> None:
        client = FlapiClient("http://fake")
        client.search = AsyncMock(return_value=[])  # type: ignore[method-assign]

        with pytest.raises(LookupError):
            await client.get_display_name(42)

    async def test_raises_when_name_missing(self) -> None:
        client = FlapiClient("http://fake")
        client.search = AsyncMock(return_value=[{"Id": 42}])  # type: ignore[method-assign]

        with pytest.raises(LookupError):
            await client.get_display_name(42)


class TestFetchDataSource:
    async def test_raises_when_not_found(self) -> None:
        client = FlapiClient("http://fake")
        client.search = AsyncMock(return_value=[])  # type: ignore[method-assign]

        with pytest.raises(LookupError):
            await client.fetch_data_source("42")

    async def test_returns_name_and_sample_data(self) -> None:
        client = FlapiClient("http://fake")
        client.search = AsyncMock(return_value=[{"Name": "People"}])  # type: ignore[method-assign]
        client.run_data_source = AsyncMock(return_value={"rows": [1, 2]})  # type: ignore[method-assign]

        name, data = await client.fetch_data_source("4", authorization="admin")
        assert name == "People"
        assert data == {"rows": [1, 2]}
