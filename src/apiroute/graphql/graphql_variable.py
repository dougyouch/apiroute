from typing import NamedTuple


class GraphQLVariable(NamedTuple):
    """A variable an operation declares: `$first: Int = 10` is ("first", "Int", False, True)."""

    name: str
    type: str
    # Non-null and without a default: the server rejects the operation without it
    required: bool
    has_default: bool
