class EditApplyError(ValueError):
    pass


def apply_edits(content: str, edits: list[tuple[str, str]]) -> str:
    """Apply search/replace pairs in order. Each search must match exactly one place."""
    if not edits:
        raise EditApplyError("no search/replace pairs were given.")
    for i, (search, replace) in enumerate(edits, start=1):
        label = "the search string" if len(edits) == 1 else f"search block {i}"
        matches = content.count(search) if search else 0
        if matches == 0:
            raise EditApplyError(f"{label} was not found. Copy it exactly from the current file, including whitespace.")
        if matches > 1:
            raise EditApplyError(
                f"{label} matches {matches} places. Include surrounding lines so it matches exactly one."
            )
        content = content.replace(search, replace, 1)
    return content
