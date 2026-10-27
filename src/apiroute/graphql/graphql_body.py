import json
from typing import Any

CONTENT_TYPE = "application/json"


class GraphQLBody:
    """A body_format that sends a GraphQL operation: the route's body is its variables, which
    go out with the document as {"query", "operationName", "variables"}.

    A variable whose value is None is left out, so the document's default for it applies
    (GraphQL treats an explicit null as overriding the default)."""

    encodes_empty = True  # an operation without variables still sends its query

    def __init__(self, document: str, operation_name: str | None):
        self._document = document
        self._operation_name = operation_name

    def __call__(self, client: Any, data: Any) -> tuple[bytes, str]:
        payload: dict[str, Any] = {"query": self._document}
        if self._operation_name is not None:
            payload["operationName"] = self._operation_name
        variables = data or {}
        payload["variables"] = {
            name: value for name, value in variables.items() if value is not None
        }
        return json.dumps(payload).encode(), CONTENT_TYPE
