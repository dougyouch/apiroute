from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec


class AsyncRecordingTransport:
    """RecordingTransport for async calls."""

    def __init__(self, inner: Any, record: Callable[[httpx.Response], None]):
        self._inner = inner
        self._record = record

    async def send(self, spec: RequestSpec) -> httpx.Response:
        response = await self._inner.send(spec)
        self._record(response)
        return response

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        return self._stream(spec)

    @asynccontextmanager
    async def _stream(self, spec: RequestSpec) -> AsyncIterator[httpx.Response]:
        async with self._inner.stream(spec) as response:
            await response.aread()
            self._record(response)
            yield response

    async def aclose(self) -> None:
        await self._inner.aclose()
