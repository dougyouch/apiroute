from typing import Any, NamedTuple


class CollectedDefinition(NamedTuple):
    """An operation or fragment read from an operation file: the parsed node (without any
    @paginate), the section its file belongs to ("" for the root), the # comment block written
    just above it, and where its @paginate was."""

    node: Any
    section: str
    comment: str
    paginate: Any = None  # a PaginateMark
