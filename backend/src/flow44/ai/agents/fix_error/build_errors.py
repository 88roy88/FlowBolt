import re

# tsc:  src/components/Foo.tsx(12,5): error TS2304: Cannot find name 'x'.
_TSC_ERROR_START = re.compile(r"^(?P<file>[^\s(]+)\(\d+,\d+\): error ")


def _tsc_error_blocks(output: str) -> list[tuple[str, str]]:
    """Split tsc output into (file, error text) blocks, keeping each error's indented continuation lines."""
    blocks: list[tuple[str, list[str]]] = []
    in_block = False
    for line in output.splitlines():
        match = _TSC_ERROR_START.match(line)
        if match:
            blocks.append((match.group("file").replace("\\", "/"), [line]))
            in_block = True
        elif in_block and (not line.strip() or line[0].isspace()):
            blocks[-1][1].append(line)
        else:
            in_block = False
    return [(file, "\n".join(lines).rstrip()) for file, lines in blocks]


def drop_baseline_errors(errors: str, baseline: str, keep_files: set[str]) -> str:
    """Remove tsc errors that already existed before the fix.

    Errors in ``keep_files`` (the error file and files the fix changed) are always kept, since their line
    numbers may have shifted. Output that isn't tsc-formatted is returned unchanged.
    """
    blocks = _tsc_error_blocks(errors)
    if not blocks or not baseline:
        return errors

    baseline_blocks = {text for _, text in _tsc_error_blocks(baseline)}
    kept = [text for file, text in blocks if file in keep_files or text not in baseline_blocks]
    return "\n".join(kept)
