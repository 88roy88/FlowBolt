"""Tests for Jinja prompt template rendering."""

from __future__ import annotations

from flow44.ai.agents.execute.prompts import render_codegen, render_fix_errors, render_merge, render_summary
from flow44.ai.agents.fix_error.prompts import render_fix_error_direct
from flow44.ai.agents.followup.prompts import render_followup
from flow44.ai.agents.plan.prompts import render_architecture, render_user_plan
from flow44.ai.generated_app_contract import generated_app_path_safety_prompt_context
from flow44.db.project_data_source import DataSourceContext


class TestPromptRendering:
    def test_architecture_basic(self) -> None:
        result = render_architecture()
        assert "software architect" in result
        assert "JSON" in result
        assert "components" in result
        assert result.count("## File Safety Rules") == 1

    def test_architecture_with_data_sources(self) -> None:
        sources = [
            DataSourceContext(
                data_source_id="123",
                data_source_name="Sales Data",
                sanitized_name="SalesData",
                relevant_fields="date, amount",
                data_characteristics="time-series",
                sample_data={"records": [{"date": "2024-01", "amount": 100}]},
                integration_notes="Use fetch",
                queries=[
                    {
                        "name": "records",
                        "display_name": "Records",
                        "description": "Sales records",
                        "fields": [
                            {"name": "date", "display_name": "Date", "type": "datetime", "description": None},
                            {"name": "amount", "display_name": "Amount", "type": "double", "description": None},
                        ],
                    }
                ],
                params_info={"parameters": [], "require_any": False},
            )
        ]
        result = render_architecture(data_source_contexts=sources)
        assert "Sales Data" in result
        assert "following data sources" in result
        assert "dataSourceSalesData" in result
        assert "Pre-generated file" in result

    def test_architecture_without_data_sources(self) -> None:
        result = render_architecture(data_source_contexts=None)
        assert "Data Source Integration" not in result

    def test_merge_without_data_sources(self) -> None:
        result = render_merge(has_data_sources=False)
        assert "Pre-Generated Files" not in result
        assert result.count("## File Safety Rules") == 1

    def test_merge_with_data_sources(self) -> None:
        result = render_merge(has_data_sources=True)
        assert "Pre-Generated Files" in result

    def test_user_plan_basic(self) -> None:
        result = render_user_plan()
        assert "friendly project manager" in result
        assert "feedback" not in result.lower() or "user_feedback" not in result

    def test_user_plan_with_feedback(self) -> None:
        result = render_user_plan(has_feedback=True)
        assert "feedback" in result.lower()

    def test_summary(self) -> None:
        result = render_summary()
        assert "summary" in result.lower()
        assert "tech_stack" in result

    def test_followup(self) -> None:
        result = render_followup(
            project_summary="A todo app built with React",
            file_tree="src/\n  App.tsx\n  Todo.tsx",
        )
        assert "todo app" in result
        assert "App.tsx" in result
        assert "EXPLORE" in result
        assert result.count("## File Safety Rules") == 1

    def test_codegen(self) -> None:
        result = render_codegen(
            task_title="Create Header",
            task_description="Build the header component",
            task_files=["src/Header.tsx"],
            architecture={"components": [{"name": "Header"}]},
            ux_design={"layout": "Top navigation bar"},
        )
        assert "Create Header" in result
        assert "src/Header.tsx" in result
        assert "flowArtifact" in result
        assert result.count("## File Safety Rules") == 1
        file_safety = generated_app_path_safety_prompt_context()
        for section in file_safety.values():
            for protected_entry in section:
                assert f"`{protected_entry}`" in result

    def test_codegen_with_dependencies(self) -> None:
        result = render_codegen(
            task_title="Build App",
            task_description="Main app component",
            task_files=["src/App.tsx"],
            architecture={},
            ux_design={},
            dependency_files={"src/types.ts": "export interface Todo { id: string }"},
        )
        assert "Direct dependency" in result or "dependency" in result.lower()
        assert "Todo" in result

    def test_codegen_with_data_sources(self) -> None:
        result = render_codegen(
            task_title="Dashboard",
            task_description="Build dashboard",
            task_files=["src/Dashboard.tsx"],
            architecture={},
            ux_design={},
            data_source_contexts=[
                DataSourceContext(
                    data_source_id="456",
                    data_source_name="Analytics",
                    sanitized_name="Analytics",
                    relevant_fields="metric, value",
                    data_characteristics="Real-time",
                    sample_data={"rows": [{"metric": "users", "value": 100}]},
                    integration_notes="Poll every 30s",
                    queries=[
                        {
                            "name": "metrics",
                            "display_name": "Metrics",
                            "description": "Per-metric rows",
                            "fields": [
                                {"name": "metric", "display_name": "Metric", "type": "string", "description": None},
                                {"name": "value", "display_name": "Value", "type": "int", "description": None},
                            ],
                        }
                    ],
                    params_info={"parameters": [], "require_any": False},
                )
            ],
        )
        assert "Analytics" in result
        assert "dataSourceAnalytics" in result
        assert "pre-generated" in result.lower()

    def test_fix_prompts_include_file_safety_rules_once(self) -> None:
        execute_fix = render_fix_errors(errors="broken", files={"src/App.tsx": "broken"})
        direct_fix = render_fix_error_direct(error_message="broken", files={"src/App.tsx": "broken"})

        assert execute_fix.count("## File Safety Rules") == 1
        assert direct_fix.count("## File Safety Rules") == 1
