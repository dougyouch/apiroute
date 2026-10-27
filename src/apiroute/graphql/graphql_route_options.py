from typing import Any, NamedTuple


class GraphQLRouteOptions(NamedTuple):
    """What graphql_route(...) was given, before the document is read."""

    document: str
    path: str
    data: str | None
    variables: dict[str, str]
    errors: str
    model: Any
    headers: dict[str, Any] | None
    timeout: float | None
    operation_name: str | None
    idempotent: bool | None
    validate: bool = True
    paginate: str | None = None
    cursor: str = "after"
