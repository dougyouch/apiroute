from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import httpx

from apiroute.rate_limiting.rate_limiter import RateLimiter
from apiroute.request_spec import RequestSpec


class AsyncRateLimitedTransport:
    """RateLimitedTransport for async calls: the wait doesn't block the event loop."""

    def __init__(self, inner: Any, limiter: RateLimiter, sleep: Callable[[float], Awaitable[Any]]):
        self._inner = inner
        self._limiter = limiter
        self._sleep = sleep

    async def send(self, spec: RequestSpec) -> httpx.Response:
        await self._wait()
        response = await self._inner.send(spec)
        self._limiter.observe(response)
        return response

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        return self._stream(spec)

    @asynccontextmanager
    async def _stream(self, spec: RequestSpec) -> AsyncIterator[httpx.Response]:
        await self._wait()
        async with self._inner.stream(spec) as response:
            self._limiter.observe(response)
            yield response

    async def _wait(self) -> None:
        delay = self._limiter.reserve()
        if delay > 0:
            await self._sleep(delay)
