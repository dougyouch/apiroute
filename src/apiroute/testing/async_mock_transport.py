from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.httpx_client_transport import request_arguments

if TYPE_CHECKING:
    from apiroute.testing.mock_transport import MockTransport


class AsyncMockTransport:
    """The async side of a MockTransport (its .aio), answering from the same routes and queue."""

    def __init__(self, mock: "MockTransport"):
        self.mock = mock

    async def send(self, spec: RequestSpec) -> httpx.Response:
        async with self._http_client(spec) as client:
            return await client.request(spec.method, spec.url, **request_arguments(spec))

    @asynccontextmanager
    async def stream(self, spec: RequestSpec) -> AsyncIterator[httpx.Response]:
        async with self._http_client(spec) as client:
            async with client.stream(spec.method, spec.url, **request_arguments(spec)) as response:
                yield response

    async def aclose(self) -> None:
        pass

    def _http_client(self, spec: RequestSpec) -> httpx.AsyncClient:
        handler = httpx.MockTransport(lambda request: self.mock.answer(spec, request))
        return httpx.AsyncClient(transport=handler, trust_env=False)
