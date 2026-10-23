def import_names(names: list[str] | set[str]) -> str:
    """Names for a from-import, ordered as ruff's isort does by default: constants, then
    classes, then everything else, each case-insensitively."""
    return ", ".join(sorted(set(names), key=_key))


def _key(name: str) -> tuple[int, str]:
    if name.isupper() and len(name) > 1:
        kind = 0
    elif name[:1].isupper():
        kind = 1
    else:
        kind = 2
    return kind, name.lower()
