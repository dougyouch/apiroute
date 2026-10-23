from typing import Any, NamedTuple


class RouteSpec(NamedTuple):
    """The options given to @route, before they are checked against the method's signature."""

    method: str | None
    path: str
    query: Any
    body: Any
    expected: int | tuple[int, ...] | None
    returns: str
    timeout: float | None
    stream: str | None = None
