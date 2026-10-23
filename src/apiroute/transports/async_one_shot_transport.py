from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.async_httpx_client_transport import AsyncHttpxClientTransport
from apiroute.transports.httpx_client_factory import HttpxClientFactory


class AsyncOneShotTransport:
    """A new connection for every async request, closed once the response is read.

    The default for client.aio calls, as OneShotTransport is for sync ones.
    """

    def __init__(self, **httpx_options: Any):
        self._factory = HttpxClientFactory(**httpx_options)

    async def send(self, spec: RequestSpec) -> httpx.Response:
        async with self._factory.new_async_client() as http_client:
            return await AsyncHttpxClientTransport(http_client).send(spec)

    @asynccontextmanager
    async def stream(self, spec: RequestSpec) -> AsyncIterator[httpx.Response]:
        """The connection stays open until the streamed body is done with."""
        async with self._factory.new_async_client() as http_client:
            async with AsyncHttpxClientTransport(http_client).stream(spec) as response:
                yield response

    async def aclose(self) -> None:
        pass
