import logging
from pathlib import PurePosixPath, PureWindowsPath
from typing import NamedTuple, TypedDict

logger = logging.getLogger(__name__)


class FileSafetyError(ValueError):
    pass


class ProtectedFileRules(TypedDict):
    protected_paths: list[str]
    protected_patterns: list[str]


class ScreenedFiles(NamedTuple):
    safe: list[tuple[str, str]]
    rejections: list[FileSafetyError]


_PROTECTED_APP_FILE_PATHS: tuple[str, ...] = (
    "src/main.tsx",
    "src/config.ts",
    "src/vite-env.d.ts",
)

_PROTECTED_APP_FILE_PATTERNS: tuple[str, ...] = (
    "src/api/**",
    "src/auth/**",
    "src/platform/**",
    "**/package.json",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
    "**/index.html",
    "**/.env*",
    "**/vite.config.*",
    "**/*template-guard*",
    "**/*template_guard*",
)

# Protected patterns that can diverge per project.
_SYNC_EXCLUDED_PATTERNS: frozenset[str] = frozenset(
    {
        "**/index.html",
        "**/package.json",
        "**/pnpm-lock.yaml",
        "**/.env*",
        "**/vite.config.*",  # configured per project with stamp_vite.config.
        "src/main.tsx",  # can potentially contain package context tags
        "src/config.ts",  # debatable, but people might be tempted to put consts here manually.
    }
)

# Protected paths/patterns that are safe to overwrite verbatim from the template.
SYNCABLE_TEMPLATE_FILE_PATTERNS: frozenset[str] = (
    frozenset(_PROTECTED_APP_FILE_PATHS) | frozenset(_PROTECTED_APP_FILE_PATTERNS)
) - _SYNC_EXCLUDED_PATTERNS


def _is_protected(normalized_path: str) -> bool:
    path = PurePosixPath(normalized_path)
    return any(
        path.full_match(p, case_sensitive=False) for p in (*_PROTECTED_APP_FILE_PATHS, *_PROTECTED_APP_FILE_PATTERNS)
    )


def protected_file_rules() -> ProtectedFileRules:
    return {
        "protected_paths": list(_PROTECTED_APP_FILE_PATHS),
        "protected_patterns": list(_PROTECTED_APP_FILE_PATTERNS),
    }


def normalized_path_or_reject(path: str) -> str:
    parsed = PureWindowsPath(path)
    if parsed.drive or parsed.root or not parsed.parts or ".." in parsed.parts:
        raise FileSafetyError(f"Unsafe generated file path: {path}")
    normalized = parsed.as_posix()
    if _is_protected(normalized):
        raise FileSafetyError(f"AI generation may not edit protected file: {normalized}")
    return normalized


def screen_generated_files(generated: list[tuple[str, str]]) -> ScreenedFiles:
    safe: list[tuple[str, str]] = []
    rejections: list[FileSafetyError] = []
    for path, content in generated:
        try:
            safe.append((normalized_path_or_reject(path), content))
        except FileSafetyError as exc:
            logger.warning("Rejecting generated file: %s", exc)
            rejections.append(exc)
    return ScreenedFiles(safe, rejections)


def format_rejection_feedback(rejections: list[FileSafetyError]) -> str:
    lines = "\n".join(f"- {rejection}" for rejection in rejections)
    return (
        "These files were rejected and not written:\n"
        f"{lines}\n"
        "If a file is still needed, re-emit it in the same flowArtifact format using an allowed path."
    )
