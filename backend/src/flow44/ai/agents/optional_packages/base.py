from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import NamedTuple


class PackageRuleset(StrEnum):
    CODEGEN = "codegen_rules"
    MERGE = "merge_rules"
    FIX_ERRORS = "fix_errors_rules"
    FOLLOWUP = "followup_rules"


class OptionalPackage(NamedTuple):
    name: str
    capability: str
    packages: tuple[str, ...]
    templates_dir: Path
    use_when: str
    avoid_when: str

    def render_prompt(self, prompt: PackageRuleset) -> str | None:
        path = self.templates_dir / f"{prompt.value}.md"
        return path.read_text(encoding="utf-8").strip() if path.is_file() else None
