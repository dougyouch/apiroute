from typing import Any, NamedTuple


class PaginateMark(NamedTuple):
    """Where an operation's @paginate sits: the steps from the operation down to the field
    (("field", node) for each field, ("on", type name or None) for each inline fragment) and
    the field itself, as parsed."""

    steps: tuple[tuple[str, Any], ...]
    field: Any

    @property
    def path(self) -> str:
        """The dotted response keys to the connection, as graphql_route(paginate=) takes."""
        return ".".join(_key(node) for kind, node in self.steps if kind == "field")


def _key(node: Any) -> str:
    return node.alias.value if node.alias else node.name.value
