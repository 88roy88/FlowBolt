from flow44.sandbox.main import SearchableSandbox


async def glob(sandbox: SearchableSandbox, pattern: str) -> str:
    # TODO: move prompt here (shared pronpt)
    # TODO: move formatting here, the sandbox should return raw results.
    results = await sandbox.glob(pattern)
    if not results:
        return "No files found matching pattern."
    return "\n".join(results)
