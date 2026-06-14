"""Backend-enforced safety and dependency contract for AI-generated app files."""

from __future__ import annotations

import re
from pathlib import PurePosixPath


class GeneratedAppContractError(ValueError):
    """Raised when generated output violates the app-generation contract."""


_PROTECTED_FILES = {
    "bun.lock",
    "bun.lockb",
    "composer.lock",
    "index.html",
    "npm-shrinkwrap.json",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "yarn.lock",
}
_PROTECTED_SRC_PATHS = {
    "src/config.ts",
    "src/main.tsx",
    "src/vite-env.d.ts",
}
_PROTECTED_SRC_DIRS = {
    ("src", "api"),
    ("src", "auth"),
    ("src", "datasources"),
    ("src", "platform"),
}
_PROTECTED_ROOT_DIRS = {
    ".circleci",
    ".github",
    ".gitlab",
    "backend",
    "deployment",
    "infrastructure",
    "server",
}
_IMPORT_PATTERNS = (
    re.compile(r"""(?:import|export)\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']"""),
    re.compile(r"""import\s*\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""require\s*\(\s*["']([^"']+)["']\s*\)"""),
    re.compile(r"""@import\s+(?:url\()?["']([^"']+)["']"""),
)


def normalize_generated_path(path: str) -> str:
    """Normalize a generated path and reject absolute or traversal paths."""
    if path.startswith(("/", "\\")):
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    normalized = path.replace("\\", "/").lstrip("/")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise GeneratedAppContractError(f"Unsafe generated file path: {path}")
    return str(PurePosixPath(*parts))


def is_generated_app_file_allowed(path: str) -> bool:
    """Return whether AI generation may edit a path."""
    try:
        normalized = normalize_generated_path(path)
    except GeneratedAppContractError:
        return False

    parts = tuple(part.lower() for part in PurePosixPath(normalized).parts)
    name = parts[-1].lower()
    return not (
        name in _PROTECTED_FILES
        or normalized.lower() in _PROTECTED_SRC_PATHS
        or name.startswith((".env", "vite.config."))
        or parts[0] in _PROTECTED_ROOT_DIRS
        or (len(parts) >= 2 and parts[:2] in _PROTECTED_SRC_DIRS)
        or "template-guard" in name
        or "template_guard" in name
    )


def assert_generated_app_file_allowed(path: str) -> str:
    """Return a normalized path or raise for a protected target."""
    normalized = normalize_generated_path(path)
    if not is_generated_app_file_allowed(normalized):
        raise GeneratedAppContractError(f"AI generation may not edit protected file: {normalized}")
    return normalized


def external_imports(content: str) -> set[str]:
    """Extract external module specifiers from TypeScript/JavaScript source."""
    imports: set[str] = set()
    for pattern in _IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            specifier = match.group(1)
            if not specifier.startswith((".", "/")):
                imports.add(specifier)
    return imports


def disallowed_external_imports(content: str, allowed_imports: list[str]) -> set[str]:
    """Return external imports not covered by the explicit dependency contract."""
    allowed = {"react", "react-dom", *allowed_imports}
    return {
        specifier
        for specifier in external_imports(content)
        if not any(specifier == package or specifier.startswith(f"{package}/") for package in allowed)
    }


def assert_generated_code_contract(path: str, content: str, allowed_imports: list[str]) -> str:
    """Validate a generated file target and its external imports."""
    normalized = assert_generated_app_file_allowed(path)
    disallowed = sorted(disallowed_external_imports(content, allowed_imports))
    if disallowed:
        raise GeneratedAppContractError(
            f"Generated file {normalized} imports unselected packages: {', '.join(disallowed)}"
        )
    return normalized
