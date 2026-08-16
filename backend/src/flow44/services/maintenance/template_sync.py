import os
from pathlib import PurePosixPath

from flow44.ai.file_safety import SYNCABLE_TEMPLATE_FILE_PATTERNS
from flow44.sandbox.constants import SKIP_DIRS


def sync_protected_template_files(workspace_dir: str, template_dir: str) -> str:
    """Overwrite each project's framework/auth files with the template's version if they differ.

    See flow44.ai.file_safety.SYNCABLE_TEMPLATE_FILE_PATTERNS for what's in scope and why.
    """
    if not os.path.isdir(workspace_dir):
        return "workspace not present on this pod, skipped"

    updated: list[str] = []
    created: list[str] = []
    already_synced: list[str] = []
    failed: list[str] = []
    for rel_path in _get_template_files_to_sync(template_dir):
        template_path = os.path.join(template_dir, rel_path)
        project_path = os.path.join(workspace_dir, rel_path)
        try:
            with open(template_path, "rb") as f:
                template_content = f.read()
        except OSError:
            failed.append(rel_path)
            continue

        try:
            with open(project_path, "rb") as f:
                project_content = f.read()
        except FileNotFoundError:
            project_content = None
        except OSError:
            failed.append(rel_path)
            continue

        if project_content == template_content:
            already_synced.append(rel_path)
            continue

        try:
            os.makedirs(os.path.dirname(project_path), exist_ok=True)
            with open(project_path, "wb") as out:
                out.write(template_content)
        except OSError:
            failed.append(rel_path)
            continue

        if project_content is None:
            created.append(rel_path)
        else:
            updated.append(rel_path)

    groups = {"updated": updated, "created": created, "already in sync": already_synced, "failed": failed}
    summary = ", ".join(f"{label} {len(paths)}" for label, paths in groups.items())
    details = ", ".join(f"{label} [{', '.join(paths)}]" for label, paths in groups.items() if paths)
    return f"{summary} -- {details}" if details else summary


def _get_template_files_to_sync(template_dir: str) -> list[str]:
    result: list[str] = []
    for root, dirs, files in os.walk(template_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            abs_path = os.path.join(root, name)
            rel_path = os.path.relpath(abs_path, template_dir).replace(os.sep, "/")
            posix_path = PurePosixPath(rel_path)
            is_synced = any(posix_path.full_match(p, case_sensitive=False) for p in SYNCABLE_TEMPLATE_FILE_PATTERNS)
            if is_synced:
                result.append(rel_path)
    return result
