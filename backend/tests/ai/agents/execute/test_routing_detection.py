"""Tests for multi-page routing detection."""

from __future__ import annotations

from flow44.ai.agents.execute.routing_detection import detect_uses_routing


class TestDetectUsesRouting:
    def test_merge_flag(self) -> None:
        assert detect_uses_routing("Simple todo app", {"uses_routing": True, "tasks": []})

    def test_task_pages_fallback(self) -> None:
        plan = {"tasks": [{"files": ["src/pages/HomePage.tsx"]}]}
        assert detect_uses_routing("Build a landing page", plan)

    def test_architecture_pages_fallback(self) -> None:
        assert detect_uses_routing(
            "Build a landing page",
            {"tasks": []},
            architecture_file_structure=["src/App.tsx", "src/pages/AboutPage.tsx"],
        )

    def test_single_page_default(self) -> None:
        plan = {"uses_routing": False, "tasks": [{"files": ["src/App.tsx"]}]}
        assert not detect_uses_routing("Build a todo list", plan)

    def test_keywords_alone_do_not_enable_routing(self) -> None:
        assert not detect_uses_routing("Build an app with a navbar and about page", {"tasks": []})
