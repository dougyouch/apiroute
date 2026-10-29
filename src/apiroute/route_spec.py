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
    model: Any = None
    headers: Any = None
    body_format: Any = None
    decoder: Any = None
    operation: str | None = None
    # False when repeating the request could repeat its effect: errors after the request may
    # have reached the server are then never retried. None: by method (GET, HEAD, OPTIONS)
    idempotent: bool | None = None
    # A header name sending one key per call (making retries safe), False to send none even
    # when the class sets idempotency_key, None to follow the class
    idempotency_key: str | bool | None = None
    # A pagination strategy (apiroute.pagination): the method then iterates every page's items
    paginate: Any = None
    # Called with each response whose status is expected; a false value but None rejects it
    check: Any = None
