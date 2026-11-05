from contextlib import AbstractContextManager
from typing import Any

import httpx

from apiroute.caching.conditional_cache import ConditionalCache
from apiroute.request_spec import RequestSpec


class CachingTransport:
    """Makes GET requests conditional on a kept response, and answers a 304 with it. Streamed
    responses pass through: their body is the caller's to read."""

    def __init__(self, inner: Any, cache: ConditionalCache):
        self._inner = inner
        self._cache = cache

    def send(self, spec: RequestSpec) -> httpx.Response:
        # resolve() takes the request as the caller made it, before the conditional headers
        response = self._inner.send(self._cache.prepare(spec))
        return self._cache.resolve(spec, response)

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        return self._inner.stream(spec)
