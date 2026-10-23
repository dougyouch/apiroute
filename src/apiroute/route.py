from typing import Any

from apiroute.namespace import current_prefix
from apiroute.route_decorator import RouteDecorator
from apiroute.route_spec import RouteSpec


def route(
    *method_and_path: str,
    query: Any = None,
    body: Any = None,
    expected: int | tuple[int, ...] | None = None,
    returns: str = "json",
    timeout: float | None = None,
    stream: str | None = None,
    model: Any = None,
    headers: dict[str, Any] | None = None,
    body_format: Any = None,
    decoder: Any = None,
    operation: str | None = None,
) -> RouteDecorator:
    """Declares an endpoint, on a def or on its own:

        @route("/users/{id}")
        def get_user(self, id: int) -> dict: ...

        get_user = route("/users/:id")  # generates get_user(self, *, id)

    Without a method, it is inferred from the route's name (create_user is a POST).
    stream="file" writes the body to the path in a `file` parameter, stream="io" to the
    writable object in an `io` parameter, and stream="iter" returns the chunks.
    model converts the JSON response (a pydantic model or dataclass, or a list of them);
    on a def, the return annotation does the same. headers are sent with this route, after
    the class's, and may hold {name} placeholders. body_format ("json", "form", "multipart"
    or a callable) overrides the class's for this route. decoder, a callable taking the
    httpx.Response, replaces JSON parsing for returns="json" (SOAP uses it to read envelopes).
    operation is the API's own name for the call, passed to hooks as RequestSpec.operation;
    it defaults to the method name.
    """
    method, path = _split(method_and_path)
    path = current_prefix() + path
    spec = RouteSpec(
        method=method,
        path=path,
        query=query,
        body=body,
        expected=expected,
        returns=returns,
        timeout=timeout,
        stream=stream,
        model=model,
        headers=headers,
        body_format=body_format,
        decoder=decoder,
        operation=operation,
    )
    return RouteDecorator(spec)


def _split(method_and_path: tuple[str, ...]) -> tuple[str | None, str]:
    if len(method_and_path) == 1:
        return None, method_and_path[0]
    if len(method_and_path) == 2:
        return method_and_path[0], method_and_path[1]
    raise TypeError("route() takes a path, or an HTTP method and a path")
