from typing import Any, NamedTuple


class CollectedDefinition(NamedTuple):
    """An operation or fragment read from an operation file: the parsed node, the section its
    file belongs to ("" for the root) and the # comment block written just above it."""

    node: Any
    section: str
    comment: str
