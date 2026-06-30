from __future__ import annotations

import pytest

from flow44.ai.agents.followup.agent import FollowUpAgent


class FakeSandbox:
    project_id = "project"

    def __init__(self, package_json: str = '{"dependencies":{}}') -> None:
        self.install_calls: list[list[str]] = []
        self._package_json = package_json

    async def read_file(self, path: str) -> str:
        assert path == "package.json"
        return self._package_json

    async def install_optional_packages(self, package_names: list[str]) -> None:
        self.install_calls.append(package_names)


@pytest.mark.asyncio
async def test_followup_reuses_packages_from_package_json() -> None:
    sandbox = FakeSandbox('{"dependencies":{"lucide-react":"latest"}}')
    agent = FollowUpAgent("project", sandbox, user_id="test-user")  # type: ignore[arg-type]

    selected = await agent._prepare_optional_packages()

    assert selected == ["lucide-react"]
    assert sandbox.install_calls == [["lucide-react"]]


@pytest.mark.asyncio
async def test_followup_makes_no_selection_call() -> None:
    """Follow-up never triggers an AI package selection — it only reads package.json."""
    sandbox = FakeSandbox('{"dependencies":{}}')
    agent = FollowUpAgent("project", sandbox, user_id="test-user")  # type: ignore[arg-type]

    # No monkeypatching needed: the agent no longer calls decide_optional_packages at all.
    selected = await agent._prepare_optional_packages()

    assert selected == []
    assert sandbox.install_calls == [[]]
