"""Protected path rules for AI-generated app files."""

from __future__ import annotations

from pathlib import PurePosixPath
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
    name_prefixes: frozenset[str]
    name_substrings: frozenset[str]

    def is_protected(self, normalized_path: str) -> bool:
        """Return whether AI generation may not edit a normalized POSIX path."""
        normalized = normalized_path.lower()
        parts = PurePosixPath(normalized).parts
        name = parts[-1]
        return (
            name in self.files
            or normalized in self.src_paths
            or any(name.startswith(prefix) for prefix in self.name_prefixes)
            or (len(parts) >= 2 and parts[:2] in self.src_dirs)
            or any(substring in name for substring in self.name_substrings)
        )

    def prompt_context(self) -> GeneratedAppPathSafetyPromptContext:
        """Return protected path rules formatted for prompt templates."""
        return {
            "protected_files": sorted(self.files),
            "protected_src_paths": sorted(self.src_paths),
            "protected_src_dirs": sorted(f"{'/'.join(path)}/*" for path in self.src_dirs),
            "protected_name_patterns": sorted(f"{prefix}*" for prefix in self.name_prefixes)
            + sorted(f"*{substring}*" for substring in self.name_substrings),
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
            ("src", "platform"),
        }
    ),
    name_prefixes=frozenset({".env", "vite.config."}),
    name_substrings=frozenset({"template-guard", "template_guard"}),
)
