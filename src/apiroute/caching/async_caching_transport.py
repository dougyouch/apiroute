from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx

from apiroute.caching.conditional_cache import ConditionalCache
from apiroute.request_spec import RequestSpec


class AsyncCachingTransport:
    """CachingTransport for async calls."""

    def __init__(self, inner: Any, cache: ConditionalCache):
        self._inner = inner
        self._cache = cache

    async def send(self, spec: RequestSpec) -> httpx.Response:
        # resolve() takes the request as the caller made it, before the conditional headers
        response = await self._inner.send(self._cache.prepare(spec))
        return self._cache.resolve(spec, response)

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        return self._inner.stream(spec)
