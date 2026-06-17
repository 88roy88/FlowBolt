from flow44.ai.agents.followup.agent import _format_generated_app_contract_error
from flow44.ai.generated_app_contract import GeneratedAppContractError


def test_followup_contract_error_includes_specific_violation_and_recovery_guidance() -> None:
    message = _format_generated_app_contract_error(
        GeneratedAppContractError("AI generation may not edit protected file: src/main.tsx")
    )

    assert message.startswith("Generated app contract violation: ")
    assert "AI generation may not edit protected file: src/main.tsx" in message
    assert "Pick an editable app source file" in message
