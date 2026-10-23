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
) -> RouteDecorator:
    """Declares an endpoint, on a def or on its own:

        @route("/users/{id}")
        def get_user(self, id: int) -> dict: ...

        get_user = route("/users/:id")  # generates get_user(self, *, id)

    Without a method, it is inferred from the route's name (create_user is a POST).
    """
    method, path = _split(method_and_path)
    return RouteDecorator(RouteSpec(method, path, query, body, expected, returns, timeout))


def _split(method_and_path: tuple[str, ...]) -> tuple[str | None, str]:
    if len(method_and_path) == 1:
        return None, method_and_path[0]
    if len(method_and_path) == 2:
        return method_and_path[0], method_and_path[1]
    raise TypeError("route() takes a path, or an HTTP method and a path")
