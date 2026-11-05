from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import httpx

from apiroute.rate_limiting.rate_limiter import RateLimiter
from apiroute.request_spec import RequestSpec


class RateLimitedTransport:
    """Waits for the rate limiter before each request, and shows it each response."""

    def __init__(self, inner: Any, limiter: RateLimiter, sleep: Callable[[float], Any]):
        self._inner = inner
        self._limiter = limiter
        self._sleep = sleep

    def send(self, spec: RequestSpec) -> httpx.Response:
        self._wait()
        response = self._inner.send(spec)
        self._limiter.observe(response)
        return response

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        return self._stream(spec)

    @contextmanager
    def _stream(self, spec: RequestSpec) -> Iterator[httpx.Response]:
        self._wait()
        with self._inner.stream(spec) as response:
            self._limiter.observe(response)
            yield response

    def _wait(self) -> None:
        delay = self._limiter.reserve()
        if delay > 0:
            self._sleep(delay)
