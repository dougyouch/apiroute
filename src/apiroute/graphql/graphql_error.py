from typing import Any

import httpx

from apiroute.api_route_error import ApiRouteError


class GraphQLError(ApiRouteError):
    """The server answered a GraphQL operation with errors. data holds whatever it resolved
    anyway (often partial, sometimes None); codes the errors' codes (extensions.code, or a
    top-level type as GitHub sends)."""

    def __init__(self, operation: str, errors: list[Any], data: Any, response: httpx.Response):
        self.operation = operation
        self.errors = errors
        self.data = data
        self.response = response
        self.codes = [code for code in map(_code, errors) if code is not None]
        super().__init__(f"{operation}: {describe_errors(errors)}")


def describe_errors(errors: list[Any]) -> str:
    """The first error's message and path, and how many more there are."""
    first = errors[0] if isinstance(errors[0], dict) else {"message": str(errors[0])}
    text = str(first.get("message", "GraphQL error"))
    path = first.get("path")
    if path:
        text += f" (at {'.'.join(map(str, path))})"
    if len(errors) > 1:
        text += f" and {len(errors) - 1} more error{'s' if len(errors) > 2 else ''}"
    return text


def _code(error: Any) -> Any:
    """extensions.code, as the spec suggests, else a top-level type, where GitHub puts its
    codes ("NOT_FOUND")."""
    if not isinstance(error, dict):
        return None
    extensions = error.get("extensions")
    code = extensions.get("code") if isinstance(extensions, dict) else None
    return code if code is not None else error.get("type")
