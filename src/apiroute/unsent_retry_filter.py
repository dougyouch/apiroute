from collections.abc import Callable

import httpx

# Errors raised once some of the request may have reached the server: repeating it could
# repeat its effect. Connect errors, connect timeouts and pool timeouts happen before sending.
MAY_HAVE_BEEN_SENT = (
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)


class UnsentRetryFilter:
    """The should_retry of a non-idempotent route: the client's own, except that an error
    after the request may have been sent is never retried."""

    def __init__(self, should_retry: Callable[[Exception, int], bool]):
        self._should_retry = should_retry

    def __call__(self, error: Exception, attempt: int) -> bool:
        if isinstance(error, MAY_HAVE_BEEN_SENT):
            return False
        return self._should_retry(error, attempt)
