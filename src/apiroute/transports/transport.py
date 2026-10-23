from contextlib import AbstractContextManager
from typing import Protocol

import httpx

from apiroute.request_spec import RequestSpec


class Transport(Protocol):
    """How requests reach the network, chosen per environment rather than per API class.

    A web server might send each request on its own connection (OneShotTransport), while a
    threaded worker keeps one connection pool per thread (ThreadLocalTransport).
    """

    def send(self, spec: RequestSpec) -> httpx.Response: ...

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        """The response with its body unread, for streaming routes."""
        ...

    def close(self) -> None: ...
