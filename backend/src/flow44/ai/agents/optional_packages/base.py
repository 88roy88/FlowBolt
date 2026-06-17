"""Base API for generated-app optional packages."""

from __future__ import annotations

from abc import ABC
from enum import StrEnum
from typing import ClassVar

from jinja2 import Environment, PackageLoader, TemplateNotFound


class OptionalPackagePrompt(StrEnum):
    CODEGEN_CONTEXT = "codegen_context"
    CODEGEN_RULES = "codegen_rules"
    CODEGEN_UNSELECTED_RULES = "codegen_unselected_rules"
    MERGE_RULES = "merge_rules"
    MERGE_UNSELECTED_RULES = "merge_unselected_rules"
    FIX_ERRORS_RULES = "fix_errors_rules"
    FIX_ERRORS_UNSELECTED_RULES = "fix_errors_unselected_rules"


class OptionalPackage(ABC):
    """Package-owned optional dependency declaration and prompt renderer."""

    name: ClassVar[str]
    capability: ClassVar[str]
    packages: ClassVar[tuple[str, ...]]
    use_when: ClassVar[str]
    avoid_when: ClassVar[str]
    strong_intent_groups: ClassVar[tuple[tuple[str, ...], ...]] = ()
    template_package: ClassVar[str | None] = None
    template_path: ClassVar[str] = "templates"

    def __init__(self) -> None:
        for attribute in ("name", "capability", "packages", "use_when", "avoid_when"):
            if not hasattr(self, attribute):
                msg = f"{self.__class__.__name__} must define {attribute}"
                raise TypeError(msg)

    @property
    def template_anchor(self) -> str:
        return self.template_package or self.__class__.__module__

    def render_prompt(self, prompt: OptionalPackagePrompt, **context: object) -> str | None:
        """Render a package-local prompt template if it exists."""
        env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML.
            loader=PackageLoader(self.template_anchor, self.template_path),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        try:
            return env.get_template(f"{prompt.value}.jinja2").render(**context).strip()
        except TemplateNotFound:
            return None

    def get_error_fix_prompt(self, **context: object) -> str | None:
        return self.render_prompt(OptionalPackagePrompt.FIX_ERRORS_RULES, **context)
