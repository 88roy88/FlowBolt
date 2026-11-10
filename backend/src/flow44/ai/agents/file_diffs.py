import difflib
from dataclasses import dataclass, field
from typing import NamedTuple


@dataclass
class FileDiff:
    path: str
    diff: str
    is_new: bool = field(default=False)
    is_deleted: bool = field(default=False)


def compute_diff(old_content: str, new_content: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


class _OriginalFile(NamedTuple):
    content: str
    is_new: bool


class DiffTracker:
    """Accumulates file changes across a run and combines repeat writes into one diff per file."""

    def __init__(self) -> None:
        self._originals: dict[str, _OriginalFile] = {}
        self._finals: dict[str, str] = {}
        self._deleted: set[str] = set()

    def record(self, path: str, old_content: str, new_content: str, *, is_new: bool) -> None:
        if path not in self._originals:
            self._originals[path] = _OriginalFile(content=old_content, is_new=is_new)
        self._finals[path] = new_content
        self._deleted.discard(path)

    def record_deletion(self, path: str, old_content: str) -> None:
        self.record(path, old_content, "", is_new=False)
        self._deleted.add(path)

    def combined_diffs(self) -> list[FileDiff]:
        diffs = []
        for path, original in self._originals.items():
            diff_str = compute_diff(original.content, self._finals[path], path)
            is_deleted = path in self._deleted and not original.is_new
            if diff_str or is_deleted:
                diffs.append(FileDiff(path=path, diff=diff_str, is_new=original.is_new, is_deleted=is_deleted))
        return diffs
