import os
import stat

from flow44.sandbox.constants import SKIP_DIRS


def fix_file_permissions(workspace_dir: str) -> str:
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
        try:
            _recreate_with_mode(path, new_mode)
            return "fixed"
        except OSError:
            return "failed"


def _recreate_with_mode(path: str, mode: int) -> None:
    """Recreate file when no permission to chmod (require write)"""
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
