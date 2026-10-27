import hashlib
import json
from typing import Any

CONTENT_TYPE = "application/json"
PERSISTED_MODES = (None, "hash", "register")


class GraphQLBody:
    """A body_format that sends a GraphQL operation: the route's body is its variables, which
    go out with the document as {"query", "operationName", "variables"}.

    A variable whose value is None is left out, so the document's default for it applies
    (GraphQL treats an explicit null as overriding the default).

    persisted, for automatic persisted queries, adds extensions.persistedQuery with the
    document's SHA-256: "hash" sends it instead of the query, "register" with it."""

    encodes_empty = True  # an operation without variables still sends its query

    def __init__(self, document: str, operation_name: str | None, persisted: str | None = None):
        if persisted not in PERSISTED_MODES:
            raise ValueError(f"persisted must be one of {PERSISTED_MODES}")
        self._document = document
        self._operation_name = operation_name
        self._persisted = persisted
        self.sha256 = hashlib.sha256(document.encode("utf-8")).hexdigest()

    def __call__(self, client: Any, data: Any) -> tuple[bytes, str]:
        payload: dict[str, Any] = {}
        if self._persisted != "hash":
            payload["query"] = self._document
        if self._operation_name is not None:
            payload["operationName"] = self._operation_name
        variables = data or {}
        payload["variables"] = {
            name: value for name, value in variables.items() if value is not None
        }
        if self._persisted is not None:
            payload["extensions"] = {"persistedQuery": {"version": 1, "sha256Hash": self.sha256}}
        return json.dumps(payload).encode(), CONTENT_TYPE
