from typing import Any

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
) -> RouteDecorator:
    """Declares an endpoint, on a def or on its own:

        @route("/users/{id}")
        def get_user(self, id: int) -> dict: ...

        get_user = route("/users/:id")  # generates get_user(self, *, id)

    Without a method, it is inferred from the route's name (create_user is a POST).
    stream="file" writes the body to the path in a `file` parameter, stream="io" to the
    writable object in an `io` parameter, and stream="iter" returns the chunks.
    model converts the JSON response (a pydantic model or dataclass, or a list of them);
    on a def, the return annotation does the same.
    """
    method, path = _split(method_and_path)
    spec = RouteSpec(method, path, query, body, expected, returns, timeout, stream, model)
    return RouteDecorator(spec)


def _split(method_and_path: tuple[str, ...]) -> tuple[str | None, str]:
    if len(method_and_path) == 1:
        return None, method_and_path[0]
    if len(method_and_path) == 2:
        return method_and_path[0], method_and_path[1]
    raise TypeError("route() takes a path, or an HTTP method and a path")
