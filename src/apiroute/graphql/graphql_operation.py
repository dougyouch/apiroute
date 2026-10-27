from typing import NamedTuple

from apiroute.graphql.graphql_variable import GraphQLVariable


class GraphQLOperation(NamedTuple):
    """One operation of a document: its type ("query" or "mutation"), its name (None when
    anonymous) and the variables it declares."""

    type: str
    name: str | None
    variables: tuple[GraphQLVariable, ...]
