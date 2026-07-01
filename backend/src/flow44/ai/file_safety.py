from __future__ import annotations

import logging
from pathlib import PurePosixPath, PureWindowsPath
from typing import TypedDict

logger = logging.getLogger(__name__)


class FileSafetyError(ValueError):
    pass


class ProtectedFileRules(TypedDict):
    protected_paths: list[str]
    protected_patterns: list[str]


_PROTECTED_APP_FILE_PATTERNS: tuple[str, ...] = (
    "src/main.tsx",
    "src/config.ts",
    "src/vite-env.d.ts",
    "src/api/**",
    "src/auth/**",
    "src/platform/**",
    "**/package.json",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
    "**/yarn.lock",
    "**/uv.lock",
    "**/index.html",
    "**/.env*",
    "**/vite.config.*",
    "**/*template-guard*",
    "**/*template_guard*",
)


def _is_protected(normalized_path: str) -> bool:
    path = PurePosixPath(normalized_path)
    return any(path.full_match(p, case_sensitive=False) for p in _PROTECTED_APP_FILE_PATTERNS)


def protected_file_rules() -> ProtectedFileRules:
    paths: list[str] = []
    patterns: list[str] = []
    for pattern in _PROTECTED_APP_FILE_PATTERNS:
        display = pattern.removeprefix("**/").replace("/**", "/*")
        (patterns if "*" in display else paths).append(display)
    return {"protected_paths": sorted(paths), "protected_patterns": sorted(patterns)}


def normalized_path_or_reject(path: str) -> str:
    parsed = PureWindowsPath(path)
    if parsed.drive or parsed.root or not parsed.parts or ".." in parsed.parts:
        raise FileSafetyError(f"Unsafe generated file path: {path}")
    normalized = parsed.as_posix()
    if _is_protected(normalized):
        raise FileSafetyError(f"AI generation may not edit protected file: {normalized}")
    return normalized


def drop_protected_files(generated: list[tuple[str, str]], *, source: str) -> list[tuple[str, str]]:
    safe: list[tuple[str, str]] = []
    for path, content in generated:
        try:
            safe.append((normalized_path_or_reject(path), content))
        except FileSafetyError:
            logger.warning("Dropping protected generated file (%s): %s", source, path)
    return safe
