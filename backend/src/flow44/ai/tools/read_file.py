from flow44.sandbox.main import FileSystemSandbox


async def read_file_with_lines(sandbox: FileSystemSandbox, path: str) -> str:
    try:
        content = await sandbox.read_file(path)
    except (FileNotFoundError, PermissionError) as e:
        return f"Error: {e}"

    lines = content.splitlines()
    if len(lines) > 500:
        numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines[:500])]
        # TODO: if we truncate, we should add a parameter for start and end line.
        numbered.append(f"\n... (truncated at 500 lines, file has {len(lines)} total)")
        return "\n".join(numbered)

    return "\n".join(f"{i + 1:4d} | {line}" for i, line in enumerate(lines))
