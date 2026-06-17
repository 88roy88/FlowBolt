"""Protected path rules for AI-generated app files."""

from __future__ import annotations

from typing import NamedTuple


class ProtectedAppFileRules(NamedTuple):
    files: frozenset[str]
    src_paths: frozenset[str]
    src_dirs: frozenset[tuple[str, ...]]
    name_prefixes: tuple[str, ...]
    name_substrings: tuple[str, ...]


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
