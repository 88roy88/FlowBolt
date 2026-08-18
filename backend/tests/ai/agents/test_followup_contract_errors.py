from flow44.ai.agents.followup.agent import _format_file_safety_error
from flow44.ai.file_safety import FileSafetyError


def test_followup_contract_error_includes_specific_violation_and_recovery_guidance() -> None:
    message = _format_file_safety_error(FileSafetyError("AI generation may not edit protected file: src/main.tsx"))

    assert message.startswith("Generated app contract violation: ")
    assert "AI generation may not edit protected file: src/main.tsx" in message
    assert "Pick an editable app source file" in message
