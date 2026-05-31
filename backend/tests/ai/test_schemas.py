"""Tests for Pydantic schema validation of LLM responses."""

from __future__ import annotations

from flow44.ai.agents.execute.models import ProjectSummary
from flow44.ai.agents.plan.models import (
    ArchitectureDesign,
    DataSourceAnalysis,
    UserPlanOverview,
    UXDesign,
)


class TestArchitectureDesign:
    def test_valid_response(self) -> None:
        data = {
            "components": [{"name": "Header", "file": "src/Header.tsx", "purpose": "Navigation bar"}],
            "data_flow": "Props down, events up",
            "file_structure": ["src/App.tsx", "src/Header.tsx"],
            "state_management": "useState for local state",
            "key_dependencies": "react, react-dom",
            "notes": "Keep it simple",
        }
        result = ArchitectureDesign.model_validate(data)
        assert len(result.components) == 1
        assert result.components[0].name == "Header"
        assert result.state_management == "useState for local state"
        assert result.uses_routing is False

    def test_uses_routing_field(self) -> None:
        result = ArchitectureDesign.model_validate({"uses_routing": True})
        assert result.uses_routing is True

    def test_extra_fields_ignored(self) -> None:
        """LLM sometimes adds fields not in our schema — should not crash."""
        data = {
            "components": [],
            "data_flow": "",
            "unexpected_field": "should be ignored",
        }
        result = ArchitectureDesign.model_validate(data)
        assert result.components == []

    def test_missing_optional_fields_get_defaults(self) -> None:
        """Minimal response with only required fields."""
        result = ArchitectureDesign.model_validate({})
        assert result.components == []
        assert result.data_flow == ""
        assert result.notes == ""


class TestUXDesign:
    def test_valid_response(self) -> None:
        data = {
            "layout": "Single page with sidebar",
            "color_scheme": "Dark mode with blue accents",
            "components_ui": [{"name": "Sidebar", "layout": "Vertical list", "interactions": "Click to navigate"}],
        }
        result = UXDesign.model_validate(data)
        assert result.layout == "Single page with sidebar"
        assert len(result.components_ui) == 1

    def test_empty_response(self) -> None:
        result = UXDesign.model_validate({})
        assert result.layout == ""
        assert result.components_ui == []


class TestUserPlanOverview:
    def test_valid_plan(self) -> None:
        data = {
            "summary": "I'll build you a todo app",
            "features": [
                {"title": "Add todos", "description": "Click to add a new todo item"},
                {"title": "Mark complete", "description": "Check off completed items"},
            ],
            "decisions": [
                {
                    "id": "d1",
                    "title": "Color theme",
                    "chosen": "Dark mode",
                    "alternatives": ["Light mode", "Auto"],
                }
            ],
        }
        result = UserPlanOverview.model_validate(data)
        assert len(result.features) == 2
        assert result.decisions[0].chosen == "Dark mode"
        assert "Light mode" in result.decisions[0].alternatives

    def test_decisions_model_dump(self) -> None:
        """Verify model_dump produces JSON-serializable output for merge prompt."""
        data = {
            "summary": "test",
            "features": [],
            "decisions": [{"id": "d1", "title": "Theme", "chosen": "Dark", "alternatives": ["Light"]}],
        }
        result = UserPlanOverview.model_validate(data)
        dumped = [d.model_dump() for d in result.decisions]
        assert dumped[0]["chosen"] == "Dark"


class TestProjectSummary:
    def test_valid_summary(self) -> None:
        data = {
            "summary": "A todo app with drag and drop",
            "tech_stack": ["React", "TypeScript", "Tailwind"],
            "features": ["Add todos", "Drag to reorder"],
            "file_overview": {"src/App.tsx": "Main app", "src/Todo.tsx": "Todo component"},
        }
        result = ProjectSummary.model_validate(data)
        assert "React" in result.tech_stack
        assert "src/App.tsx" in result.file_overview


class TestDataSourceAnalysis:
    def test_valid_analysis(self) -> None:
        data = {
            "data_schema": "Array of sales records",
            "relevant_fields": "date, amount, customer",
            "data_characteristics": "Time-series, daily",
            "integration_notes": "Use fetch API",
        }
        result = DataSourceAnalysis.model_validate(data)
        assert "sales" in result.data_schema

    def test_empty_analysis(self) -> None:
        result = DataSourceAnalysis.model_validate({})
        assert result.data_schema == ""
