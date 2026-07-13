from __future__ import annotations

import sys
from abc import ABC
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel


class OptionalPackagePrompt(StrEnum):
    CODEGEN_RULES = "codegen_rules"
    MERGE_RULES = "merge_rules"
    FIX_ERRORS_RULES = "fix_errors_rules"


class SelectedOptionalPackage(BaseModel):
    name: str
    reason: str = ""


class OptionalPackage(ABC):
    name: ClassVar[str]
    capability: ClassVar[str]
    packages: ClassVar[tuple[str, ...]]
    use_when: ClassVar[str]
    avoid_when: ClassVar[str]

    def _template_env(self) -> Environment:
        env = getattr(self, "_env", None)
        if env is None:
            module_file = sys.modules[type(self).__module__].__file__
            templates_dir = Path(module_file).parent / "templates"  # type: ignore[arg-type]
            env = Environment(  # noqa: S701 — templates are LLM prompts, not HTML
                loader=FileSystemLoader(str(templates_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self._env = env
        return env

    def render_prompt(self, prompt: OptionalPackagePrompt) -> str | None:
        try:
            return self._template_env().get_template(f"{prompt.value}.jinja2").render().strip()
        except TemplateNotFound:
            return None
