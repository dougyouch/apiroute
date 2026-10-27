from typing import Any, NamedTuple


class GraphQLProblem(NamedTuple):
    """Something wrong (or worth a warning) in an operation file, where it was found."""

    file: str
    line: int
    column: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}: {self.message}"

    @classmethod
    def at(cls, node: Any, message: str) -> "GraphQLProblem":
        """A problem at a parsed node, in the file its Source was named after. The token's
        line and column, not graphql-core's get_location, which puts a node starting a line
        at the end of the line before."""
        token = node.loc.start_token
        return cls(node.loc.source.name, token.line, token.column, message)

    @classmethod
    def from_error(cls, error: Any, file: str = "") -> "GraphQLProblem":
        """A problem from a graphql-core error, located at its first node (or location)."""
        if error.nodes and error.nodes[0].loc is not None:
            return cls.at(error.nodes[0], error.message)
        location = (error.locations or [None])[0]
        name = error.source.name if error.source is not None else file
        if location is None:
            return cls(name, 0, 0, error.message)
        return cls(name, location.line, location.column, error.message)
