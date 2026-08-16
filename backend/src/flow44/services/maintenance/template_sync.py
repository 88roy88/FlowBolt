import os
from pathlib import PurePosixPath

from flow44.ai.file_safety import SYNCABLE_TEMPLATE_FILE_PATTERNS
from flow44.sandbox.constants import SKIP_DIRS


def sync_protected_template_files(workspace_dir: str, template_dir: str) -> str:
    if not os.path.isdir(workspace_dir):
        return "workspace not present on this pod, skipped"

    groups: dict[str, list[str]] = {"updated": [], "created": [], "already in sync": [], "failed": []}
    for rel_path in _get_template_file_paths_to_sync(template_dir):
        template_path = os.path.join(template_dir, rel_path)
        project_path = os.path.join(workspace_dir, rel_path)
        status = _sync_file(template_path, project_path)
        groups[status].append(rel_path)

    summary = ", ".join(f"{label} {len(paths)}" for label, paths in groups.items())
    details = ", ".join(f"{label} [{', '.join(paths)}]" for label, paths in groups.items() if paths)
    return f"{summary} -- {details}" if details else summary


def _sync_file(template_path: str, project_path: str) -> str:
    try:
        with open(template_path, "rb") as f:
            template_content = f.read()
    except OSError:
        return "failed"

    try:
        with open(project_path, "rb") as f:
            project_content = f.read()
    except FileNotFoundError:
        project_content = None
    except OSError:
        return "failed"

    if project_content == template_content:
        return "already in sync"

    try:
        os.makedirs(os.path.dirname(project_path), exist_ok=True)
        with open(project_path, "wb") as out:
            out.write(template_content)
    except OSError:
        return "failed"

    return "created" if project_content is None else "updated"


def _get_template_file_paths_to_sync(template_dir: str) -> list[str]:
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
