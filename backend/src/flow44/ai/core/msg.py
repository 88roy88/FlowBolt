from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)


def user_msg(content: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=content)])


def assistant_msg(content: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=content)])
