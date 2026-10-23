import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

_MAX_SELECTED_ELEMENTS = 5
_MAX_COMPONENT_HIERARCHY_DEPTH = 4


def _clip(value: Any, max_len: int) -> Any:
    return value[:max_len] if isinstance(value, str) else value


class SelectedElement(BaseModel):
    tag: str = Field(min_length=1)
    selector: str = ""
    text: str = ""
    classes: str = ""
    html: str = ""
    components: list[str] = Field(default_factory=list)

    @field_validator("tag", mode="before")
    @classmethod
    def _clip_tag(cls, v: Any) -> Any:
        return _clip(v, 40)

    @field_validator("selector", mode="before")
    @classmethod
    def _clip_selector(cls, v: Any) -> Any:
        return _clip(v, 300)

    @field_validator("text", mode="before")
    @classmethod
    def _clip_text(cls, v: Any) -> Any:
        return _clip(v, 120)

    @field_validator("classes", mode="before")
    @classmethod
    def _clip_classes(cls, v: Any) -> Any:
        return _clip(v, 200)

    @field_validator("html", mode="before")
    @classmethod
    def _clip_html(cls, v: Any) -> Any:
        return _clip(v, 600)

    @field_validator("components", mode="before")
    @classmethod
    def _clip_components(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return []
        return [c[:80] for c in v if isinstance(c, str) and c][:_MAX_COMPONENT_HIERARCHY_DEPTH]


def parse_selected_elements(raw: Any) -> list[SelectedElement]:
    if not isinstance(raw, list):
        return []
    elements: list[SelectedElement] = []
    for item in raw[:_MAX_SELECTED_ELEMENTS]:
        try:
            elements.append(SelectedElement.model_validate(item))
        except ValidationError:
            logger.warning("Dropping invalid selected element: %r", item)
    return elements


def format_selected_elements(elements: list[SelectedElement]) -> str:
    lines = [
        "<selected_elements>",
        'The user selected these elements in the live preview; "this"/"these" in the message refer to them.',
    ]
    for i, el in enumerate(elements, start=1):
        head = f"{i}. <{el.tag}>"
        if el.components:
            head += f" in components: {' < '.join(el.components)}"
        lines.append(head)
        if el.selector:
            lines.append(f"   selector: {el.selector}")
        if el.classes:
            lines.append(f"   classes: {el.classes}")
        if el.text:
            lines.append(f'   text: "{el.text}"')
        if el.html:
            lines.append(f"   html: {el.html}")
    lines.append("</selected_elements>")
    return "\n".join(lines)
