import posixpath
import re

SCRIPT_EXTENSIONS = (".tsx", ".ts", ".jsx", ".js")

# A path token containing src/... with a source extension, e.g. "C:\ws\src\App.tsx:" or "/ws/src/App.tsx?t=1"
_SOURCE_PATH_RE = re.compile(r"[^\s'\"()]*src[\\/][^\s:'\"()?]+?\.(?:tsx?|jsx?|css)\b")

# import x from './a' / export { x } from '../b' / import './c'
_LOCAL_IMPORT_RE = re.compile(r"""(?:\bfrom\s+|(?<![@\w])import\s+)['"](\.{1,2}/[^'"]+)['"]""")


def find_source_path(*texts: str | None) -> str | None:
    """Return the first non-node_modules source path mentioned in the given texts."""
    for text in texts:
        for match in _SOURCE_PATH_RE.finditer(text or ""):
            if "node_modules" not in match.group(0):
                return match.group(0)
    return None


def local_import_candidates(path: str, content: str) -> list[list[str]]:
    """For each relative script import in a file, the workspace paths it may resolve to, in order."""
    if not path.endswith(SCRIPT_EXTENSIONS):
        return []

    base_dir = posixpath.dirname(path)
    candidates: list[list[str]] = []
    for spec in dict.fromkeys(_LOCAL_IMPORT_RE.findall(content)):
        target = posixpath.normpath(posixpath.join(base_dir, spec))
        if target.endswith(SCRIPT_EXTENSIONS):
            candidates.append([target])
        elif not posixpath.splitext(target)[1]:
            candidates.append(
                [target + ext for ext in SCRIPT_EXTENSIONS] + [f"{target}/index{ext}" for ext in SCRIPT_EXTENSIONS]
            )
    return candidates
