import threading
import time
from collections.abc import Callable

import httpx

from apiroute.rate_limiting.rate_limit_headers import RateLimitHeaders


class RateLimiter:
    """Keeps a client under an API's rate limit by waiting before a request, instead of
    sending it and getting a 429. Set one as a client's `rate_limiter`:

        class GitHub(Client):
            rate_limiter = RateLimiter(requests=10, per=1.0, headers=True)

    requests per `per` seconds is a token bucket holding `burst` requests (default: requests),
    so up to `burst` go at once and the rest are spread out. With headers=True, it also stops
    sending when a response says the quota is spent (RateLimit, RateLimit-Remaining or
    X-RateLimit-Remaining at 0) until it resets, and after a 429 or 503 for its Retry-After.
    Either or both may be used.

    Every request sent with it counts: retries, pages, stream reconnects. One RateLimiter is
    one budget, shared by every thread and event loop using it, so a class attribute limits
    every instance of the class together; give instances their own for separate budgets.
    Budgets are per process.
    """

    def __init__(
        self,
        requests: float | None = None,
        per: float = 1.0,
        *,
        burst: int | None = None,
        headers: bool = False,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ):
        _validate(requests, per, burst, headers)
        self._rate = None if requests is None else requests / per
        self._capacity = float(burst if burst is not None else max(1, int(requests or 1)))
        self._headers = RateLimitHeaders(wall_clock) if headers else None
        self._clock = clock
        self._lock = threading.Lock()
        self._tokens = self._capacity
        self._refilled = clock()
        self._paused_until = 0.0

    def reserve(self) -> float:
        """Takes a slot for one request; returns the seconds to wait before sending it."""
        with self._lock:
            now = self._clock()
            wait = max(0.0, self._paused_until - now)
            if self._rate is not None:
                wait = max(wait, self._take(now))
            return wait

    def observe(self, response: httpx.Response) -> None:
        """Reads a response's rate limit headers, when headers=True."""
        if self._headers is None:
            return
        pause = self._headers.pause(response)
        if pause is None:
            return
        with self._lock:
            self._paused_until = max(self._paused_until, self._clock() + pause)

    def _take(self, now: float) -> float:
        """A token bucket that may go into debt: a request that finds it empty takes a token
        anyway and waits for the bucket to refill to it, so waiting requests queue in order."""
        assert self._rate is not None
        self._tokens = min(self._capacity, self._tokens + (now - self._refilled) * self._rate)
        self._refilled = now
        self._tokens -= 1
        return 0.0 if self._tokens >= 0 else -self._tokens / self._rate


def _validate(requests: float | None, per: float, burst: int | None, headers: bool) -> None:
    if requests is None and not headers:
        raise ValueError("RateLimiter needs requests=, headers=True or both")
    if requests is not None and requests <= 0:
        raise ValueError("requests must be more than 0")
    if per <= 0:
        raise ValueError("per must be more than 0 seconds")
    if burst is not None and burst < 1:
        raise ValueError("burst must be at least 1")
