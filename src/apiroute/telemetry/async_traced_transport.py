from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.telemetry.open_telemetry import OpenTelemetry


class AsyncTracedTransport:
    """TracedTransport for async calls."""

    def __init__(self, inner: Any, telemetry: OpenTelemetry, redact_url: Callable[[str], str]):
        self._inner = inner
        self._telemetry = telemetry
        self._redact_url = redact_url

    async def send(self, spec: RequestSpec) -> httpx.Response:
        with self._telemetry.span(spec, self._redact_url) as span:
            response = await self._inner.send(span.inject(spec))
            span.record(response)
            return response

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        return self._stream(spec)

    @asynccontextmanager
    async def _stream(self, spec: RequestSpec) -> AsyncIterator[httpx.Response]:
        async with AsyncExitStack() as opening:
            with self._telemetry.span(spec, self._redact_url) as span:
                response = await opening.enter_async_context(self._inner.stream(span.inject(spec)))
                span.record(response)
            opened = opening.pop_all()
        async with opened:
            yield response
