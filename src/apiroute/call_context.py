from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from apiroute.route_definition import RouteDefinition


@dataclass(frozen=True)
class CallContext:
    """The route call whose requests are being sent: the client or section it was made on,
    and the route. Transports run inside it, so a test helper can tell which route a request
    belongs to (ResponseSchemas loads only that route's models) without searching the client.
    """

    router: Any
    definition: RouteDefinition

    @staticmethod
    def current() -> "CallContext | None":
        return _CURRENT.get()

    @contextmanager
    def active(self) -> Iterator[None]:
        token = _CURRENT.set(self)
        try:
            yield
        finally:
            _CURRENT.reset(token)


_CURRENT: ContextVar[CallContext | None] = ContextVar("apiroute_call", default=None)
