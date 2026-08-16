import os
import stat
from pathlib import PurePosixPath

from flow44.ai.file_safety import SYNCABLE_TEMPLATE_FILE_PATTERNS
from flow44.sandbox.constants import SKIP_DIRS


def fix_file_permissions(workspace_dir: str) -> str:
    """Walk workspace_dir and OR group/other write bits onto any file missing them."""
    if not os.path.isdir(workspace_dir):
        return "workspace not present on this pod, skipped"

    counts = {"fixed": 0, "already writable": 0, "failed": 0}
    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = os.path.join(root, name)
            if not os.path.islink(path):
                counts[_ensure_writable(path)] += 1

    return ", ".join(f"{label} {count}" for label, count in counts.items())


def _ensure_writable(path: str) -> str:
    """Make `path` group/other writable if it isn't. Returns "fixed", "already writable", or "failed"."""
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return "failed"

    if mode & 0o022 == 0o022:
        return "already writable"

    new_mode = mode | 0o022
    try:
        os.chmod(path, new_mode)
        return "fixed"
    except OSError:
        pass  # not the file's owner - fall back to recreating it as ourselves

    try:
        _recreate_with_mode(path, new_mode)
        return "fixed"
    except OSError:
        return "failed"


def _recreate_with_mode(path: str, mode: int) -> None:
    """Unlink and recreate `path` (preserving its content) so the current process owns it, then set `mode`.

    chmod is restricted to a file's owner (or root), so a file created by a
    different uid can't be re-permissioned directly. Unlinking only requires
    write access on the containing directory though, so recreating the file
    makes the current uid the owner and lets fchmod always succeed.
    """
    with open(path, "rb") as f:
        content = f.read()
    os.unlink(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.fchmod(fd, mode)
    except OSError:
        os.close(fd)
        raise
    with os.fdopen(fd, "wb") as out:
        out.write(content)


def sync_protected_template_files(workspace_dir: str, template_dir: str) -> str:
    """Overwrite each project's framework/auth files with the template's version if they differ.

    See flow44.ai.file_safety.SYNCABLE_TEMPLATE_FILE_PATTERNS for what's in scope and why.
    """
    if not os.path.isdir(workspace_dir):
        return "workspace not present on this pod, skipped"

    updated = 0
    created = 0
    already_synced = 0
    failed = 0
    for rel_path in _get_template_files_to_sync(template_dir):
        template_path = os.path.join(template_dir, rel_path)
        project_path = os.path.join(workspace_dir, rel_path)
        try:
            with open(template_path, "rb") as f:
                template_content = f.read()
        except OSError:
            failed += 1
            continue

        try:
            with open(project_path, "rb") as f:
                project_content = f.read()
        except FileNotFoundError:
            project_content = None
        except OSError:
            failed += 1
            continue

        if project_content == template_content:
            already_synced += 1
            continue

        try:
            os.makedirs(os.path.dirname(project_path), exist_ok=True)
            with open(project_path, "wb") as out:
                out.write(template_content)
        except OSError:
            failed += 1
            continue

        if project_content is None:
            created += 1
        else:
            updated += 1

    return f"updated {updated}, created {created}, already in sync {already_synced}, failed {failed}"


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
