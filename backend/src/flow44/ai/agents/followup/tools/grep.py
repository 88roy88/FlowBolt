from flow44.sandbox.main import SearchableSandbox


async def grep(  # noqa: PLR0911
    sandbox: SearchableSandbox,
    pattern: str,
    path: str = "/",
    file_pattern: str | None = None,
) -> str:
    # TODO: move prompt here (shared pronpt)
    # TODO: move formatting here, the sandbox should return raw results.
    try:
        matches = await sandbox.grep(pattern, path, file_pattern, max_results=50)
    except PermissionError as e:
        return f"Error: {e}"

    if not matches:
        return "No matches found."

    lines = [f"{m.file}:{m.line}:{m.content}" for m in matches]
    return "\n".join(lines)
