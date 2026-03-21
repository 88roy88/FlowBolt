from __future__ import annotations

from typing import Any, Literal, Sequence

from pydantic import BaseModel


class ContentBlock(BaseModel):
    pass


class TextContent(ContentBlock):
    type: Literal["text"] = "text"
    text: str


class ToolUseContent(ContentBlock):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultContent(ContentBlock):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


class Message(BaseModel):
    role: Literal["user", "assistant", "system", "tool"]
    content: str | Sequence[ContentBlock]

    @classmethod
    def user(cls, text: str) -> Message:
        return cls(role="user", content=text)

    @classmethod
    def assistant(cls, text: str) -> Message:
        return cls(role="assistant", content=text)

    @classmethod
    def system(cls, text: str) -> Message:
        return cls(role="system", content=text)

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str) -> Message:
        return cls(role="tool", content=content, tool_call_id=tool_call_id)

    tool_call_id: str | None = None

    # TODO: why not just model dump?
    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role}
        if isinstance(self.content, str):
            d["content"] = self.content
        else:
            d["content"] = [b.model_dump() for b in self.content]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d
