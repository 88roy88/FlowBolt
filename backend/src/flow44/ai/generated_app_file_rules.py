"""Protected path rules for AI-generated app files."""

from __future__ import annotations

PROTECTED_FILES = {
    "index.html",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "uv.lock",
    "yarn.lock",
}
PROTECTED_SRC_PATHS = {
    "src/config.ts",
    "src/main.tsx",
    "src/vite-env.d.ts",
}
PROTECTED_SRC_DIRS = {
    ("src", "api"),
    ("src", "auth"),
    ("src", "datasources"),
    ("src", "platform"),
}
PROTECTED_ROOT_DIRS = {
    ".github",
    ".gitlab",
    "backend",
}
PROTECTED_NAME_PREFIXES = (".env", "vite.config.")
PROTECTED_NAME_SUBSTRINGS = ("template-guard", "template_guard")
