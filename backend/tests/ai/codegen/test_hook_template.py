"""Tests for flow44.ai.codegen.hook_template."""

from __future__ import annotations

from flow44.ai.codegen.hook_template import generate_data_source_hook


class TestGenerateDataSourceHook:
    def test_basic_output(self) -> None:
        result = generate_data_source_hook("42", "Sales", "../types/dataSourceSales")
        # Imports
        assert "import { useState, useEffect, useCallback } from 'react';" in result
        assert "import { API_BASE } from '../config';" in result
        assert "import { credentialsStore } from '../auth';" in result
        assert "import type { SalesResponse } from '../types/dataSourceSales';" in result
        # Function
        assert "export function useDataSourceSales()" in result
        # Fetch URL with correct data source ID
        assert "/api/data-source/42/run" in result
        # Auth
        assert "credentialsStore.getValidToken()" in result
        # Return shape
        assert "return { data, isLoading, error, refetch: fetchData };" in result

    def test_different_ids(self) -> None:
        result = generate_data_source_hook("abc-123", "MyApi", "../types/dataSourceMyApi")
        assert "/api/data-source/abc-123/run" in result
        assert "useDataSourceMyApi" in result
        assert "MyApiResponse" in result

    def test_uses_api_base(self) -> None:
        """Ensure the hook uses the API_BASE variable in the fetch URL."""
        result = generate_data_source_hook("1", "X", "../types/dataSourceX")
        assert "${API_BASE}/api/data-source/1/run" in result

    def test_contains_loading_and_error_states(self) -> None:
        result = generate_data_source_hook("1", "Test", "../types/dataSourceTest")
        assert "useState(true)" in result  # isLoading starts true
        assert "useState<string | null>(null)" in result  # error starts null
        assert "setIsLoading(false)" in result  # finally block

    def test_contains_refetch(self) -> None:
        result = generate_data_source_hook("1", "Test", "../types/dataSourceTest")
        assert "refetch: fetchData" in result


class TestGenerateDataSourceFilesIntegration:
    """Test the full pipeline as PlanAgent would call it."""

    def test_produces_types_and_hook_files(self) -> None:
        from flow44.ai.agents.plan.agent import PlanAgent

        ctx = {
            "data_source_id": "7",
            "data_source_name": "Sales Dashboard",
            "sanitized_name": "SalesDashboard",
            "sample_data": {
                "results": {
                    "sales": [{"id": 1, "amount": 100}],
                }
            },
        }
        files = PlanAgent._generate_data_source_files(ctx)

        assert "src/types/dataSourceSalesDashboard.ts" in files
        assert "src/hooks/useDataSourceSalesDashboard.ts" in files

        types_content = files["src/types/dataSourceSalesDashboard.ts"]
        assert "SalesDashboardSales" in types_content
        assert "SalesDashboardResponse" in types_content

        hook_content = files["src/hooks/useDataSourceSalesDashboard.ts"]
        assert "useDataSourceSalesDashboard" in hook_content
        assert "/api/data-source/7/run" in hook_content
        assert "SalesDashboardResponse" in hook_content
