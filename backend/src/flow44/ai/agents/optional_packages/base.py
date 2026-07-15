from __future__ import annotations

import inspect
from enum import StrEnum
from pathlib import Path
from typing import ClassVar


class PackageRuleset(StrEnum):
    CODEGEN = "codegen_rules"
    MERGE = "merge_rules"
    FIX_ERRORS = "fix_errors_rules"


class OptionalPackage:
    name: ClassVar[str]
    capability: ClassVar[str]
    packages: ClassVar[tuple[str, ...]]
    use_when: ClassVar[str]
    avoid_when: ClassVar[str]

    def render_prompt(self, prompt: PackageRuleset) -> str | None:
        path = Path(inspect.getfile(type(self))).parent / "templates" / f"{prompt.value}.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else None
