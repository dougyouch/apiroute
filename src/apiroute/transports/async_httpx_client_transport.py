from contextlib import AbstractAsyncContextManager

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.httpx_client_transport import request_arguments


class AsyncHttpxClientTransport:
    """Sends through an httpx.AsyncClient you own, e.g. one with a MockTransport in tests.

    aclose() leaves the client open; closing it is up to its owner.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def send(self, spec: RequestSpec) -> httpx.Response:
        return await self.http_client.request(spec.method, spec.url, **request_arguments(spec))

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        return self.http_client.stream(spec.method, spec.url, **request_arguments(spec))

    async def aclose(self) -> None:
        pass
