from typing import Any

from langfuse.decorators import langfuse_context
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from flow44.config import settings
from flow44.db.events import emit_event
from flow44.sandbox.main import PnpmSandbox


def resolve_model(model: str | None) -> Model:
    """Create a pydantic-ai Model for the given model string.

    Supports:
      - ``anthropic:model-id`` → Anthropic API (direct, uses ANTHROPIC_API_KEY env var)
      - ``bedrock:model-id``   → AWS Bedrock (native provider)
      - anything else          → OpenAI-compatible endpoint (vLLM, Ollama, OpenRouter)
                                 configured via AI_BASE_URL / AI_API_KEY
    """
    name = model or settings.AI_MODEL
    print(f"Resolving model '{name}'")

    if name.startswith("anthropic:"):
        from pydantic_ai.models.anthropic import AnthropicModel  # noqa: PLC0415

        return AnthropicModel(name.removeprefix("anthropic:"))

    if name.startswith("bedrock:"):
        from pydantic_ai.models.bedrock import BedrockConverseModel  # noqa: PLC0415

        return BedrockConverseModel(name.removeprefix("bedrock:"))

    return OpenAIChatModel(
        name,
        provider=OpenAIProvider(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY,
        ),
    )


class BaseAgent:
    def __init__(
        self,
        project_id: str,
        sandbox: PnpmSandbox,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        if sandbox.project_id != project_id:
            raise ValueError(f"Sandbox project_id '{sandbox.project_id}' doesn't match agent project_id '{project_id}'")

        self.project_id = project_id
        self.sandbox = sandbox
        self.model = model
        self._trace_id = trace_id

    async def emit(self, event: dict[str, Any]) -> None:
        await emit_event(self.project_id, event)

    def _llm_metadata(self, generation_name: str) -> dict[str, Any]:
        trace_id = self._trace_id or langfuse_context.get_current_trace_id()
        observation_id = langfuse_context.get_current_observation_id()
        return {
            "existing_trace_id": trace_id,
            "parent_observation_id": observation_id,
            "generation_name": generation_name,
        }
