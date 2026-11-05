from collections.abc import Callable
from typing import Any

import httpx

from apiroute.retry_policy import RetryPolicy


class StreamReconnector:
    """Reopens an event stream whose connection failed mid-body, as the call's retry policy
    allows: the same request, with Last-Event-ID set to the last event ID the stream sent, after
    the backoff delay or the server's `retry:` time, whichever is longer.

    `attempt` counts the failures since an event was last received; the policy's should_retry
    decides, so a route that isn't idempotent never reconnects after an error mid-body.
    """

    def __init__(
        self,
        policy: RetryPolicy,
        sleep: Callable[[float], Any],
        reopen: Callable[[dict[str, str]], Any],
    ):
        self._policy = policy
        self._sleep = sleep
        self._reopen = reopen

    def reopen(self, error: Exception, attempt: int, decoder: Any) -> tuple[httpx.Response, Any]:
        """The reopened response and the stack that closes it; raises error when the policy
        says stop."""
        self._sleep(self.delay(error, attempt, decoder))
        return self._reopen(self.resume_headers(decoder))

    def delay(self, error: Exception, attempt: int, decoder: Any) -> float:
        delay = self._policy.delay_before_retry(error, attempt)
        if delay is None:
            raise error
        if decoder.retry is None:
            return delay
        return max(delay, decoder.retry / 1000)

    @staticmethod
    def resume_headers(decoder: Any) -> dict[str, str]:
        return {"Last-Event-ID": decoder.last_event_id} if decoder.last_event_id else {}
