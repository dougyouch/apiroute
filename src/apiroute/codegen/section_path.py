def section_folder(group_name: str) -> str:
    """A section's folder in the package: issuing.cards -> issuing/cards ("" for the root)."""
    return group_name.replace(".", "/")


def section_depth(group_name: str) -> int:
    """How many folders below the package's root a section is: 0 for the root."""
    return group_name.count(".") + 1 if group_name else 0
