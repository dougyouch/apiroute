from contextlib import AbstractAsyncContextManager
from typing import Protocol

import httpx

from apiroute.request_spec import RequestSpec


class AsyncTransport(Protocol):
    """The async counterpart of Transport, used by calls through client.aio."""

    async def send(self, spec: RequestSpec) -> httpx.Response: ...

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        """The response with its body unread, for streaming routes."""
        ...

    async def aclose(self) -> None: ...
