"""Shared constants for sandbox file operations, search, and display."""

# Directories excluded from file listing, glob, and search results.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        ".next",
        "dist",
        ".cache",
        "__pycache__",
        ".vite",
    }
)

# Lock files excluded from search results (too large / not useful to search).
_SKIP_LOCK_FILES: tuple[str, ...] = (
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "bun.lockb",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
)

# ripgrep --glob exclude patterns derived from SKIP_DIRS and lock files.
GREP_SKIP_GLOBS: list[str] = [f"!{d}" for d in sorted(SKIP_DIRS)] + [f"!{f}" for f in _SKIP_LOCK_FILES]
