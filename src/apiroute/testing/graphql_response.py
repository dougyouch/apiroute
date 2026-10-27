from typing import Any

import httpx

_UNSET: Any = object()


def graphql_response(
    data: Any = _UNSET,
    errors: list[Any] | None = None,
    status: int = 200,
    extensions: dict[str, Any] | None = None,
) -> httpx.Response:
    """A GraphQL response for a MockTransport to answer with:

        mock.on(operation="Viewer").respond(graphql_response(data={"viewer": {"login": "a"}}))
        mock.respond(graphql_response(errors=[{"message": "Not allowed"}]))

    With errors and no data, data is null, as servers send it."""
    body: dict[str, Any] = {}
    if data is not _UNSET or errors is not None:
        body["data"] = None if data is _UNSET else data
    if errors is not None:
        body["errors"] = errors
    if extensions is not None:
        body["extensions"] = extensions
    return httpx.Response(status, json=body)
