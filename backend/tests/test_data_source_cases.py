"""Tests for data-source integration helpers."""

from __future__ import annotations

import pytest

from flow44.integrations import data_source_cases
from flow44.integrations.data_source_cases import normalize_data_source_authorization


class TestDataSourceCases:
    def test_normalize_data_source_authorization(self) -> None:
        assert normalize_data_source_authorization(None) is None
        assert normalize_data_source_authorization("   ") is None
        assert normalize_data_source_authorization("  Bearer token  ") == "Bearer token"

    async def test_get_data_source_display_name_prefers_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(query_or_id: str, *, authorization: str | None):
            assert query_or_id == "42"
            assert authorization == "Bearer x"
            return [{"Name": "  Sales Overview  "}]

        monkeypatch.setattr(data_source_cases, "search_data_sources", _fake_search)

        result = await data_source_cases.get_data_source_display_name(42, authorization="Bearer x")
        assert result == "Sales Overview"

    async def test_fetch_data_source_data_raises_when_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_search(query_or_id: str, *, authorization: str | None):
            return []

        monkeypatch.setattr(data_source_cases, "search_data_sources", _fake_search)

        with pytest.raises(LookupError, match="Data source 42 not found"):
            await data_source_cases.fetch_data_source_data("42", authorization=None)
