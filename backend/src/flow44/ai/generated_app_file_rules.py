"""Protected path rules for AI-generated app files."""

from __future__ import annotations

from typing import NamedTuple, TypedDict


class GeneratedAppPathSafetyPromptContext(TypedDict):
    protected_files: list[str]
    protected_src_paths: list[str]
    protected_src_dirs: list[str]
    protected_name_patterns: list[str]


class ProtectedAppFileRules(NamedTuple):
    files: frozenset[str]
    src_paths: frozenset[str]
    src_dirs: frozenset[tuple[str, ...]]
    name_prefixes: tuple[str, ...]
    name_substrings: tuple[str, ...]

    def prompt_context(self) -> GeneratedAppPathSafetyPromptContext:
        """Return protected path rules formatted for prompt templates."""
        return {
            "protected_files": sorted(self.files),
            "protected_src_paths": sorted(self.src_paths),
            "protected_src_dirs": sorted(f"{'/'.join(path)}/*" for path in self.src_dirs),
            "protected_name_patterns": [f"{prefix}*" for prefix in self.name_prefixes]
            + [f"*{substring}*" for substring in self.name_substrings],
        }


PROTECTED_APP_FILE_RULES = ProtectedAppFileRules(
    files=frozenset(
        {
            "index.html",
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "uv.lock",
            "yarn.lock",
        }
    ),
    src_paths=frozenset(
        {
            "src/config.ts",
            "src/main.tsx",
            "src/vite-env.d.ts",
        }
    ),
    src_dirs=frozenset(
        {
            ("src", "api"),
            ("src", "auth"),
            ("src", "datasources"),
            ("src", "platform"),
        }
    ),
    name_prefixes=(".env", "vite.config."),
    name_substrings=("template-guard", "template_guard"),
)
