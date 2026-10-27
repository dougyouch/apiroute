import logging
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from apiroute.retries import Retries
from apiroute.unexpected_response import UnexpectedResponse

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Decides whether a failed attempt is retried and how long to wait first.

    Shared by the sync and async retry loops, which differ only in how they sleep.
    Every failure is logged, retried or not: at WARNING, or at the level an exception declares
    in a log_level attribute (an expected protocol reply, such as a persisted-query miss).
    """

    def __init__(
        self, retries: Retries, should_retry: Callable[[Exception, int], bool], route_name: str
    ):
        self._retries = retries
        self._should_retry = should_retry
        self._route_name = route_name

    def delay_before_retry(self, error: Exception, attempt: int) -> float | None:
        """Seconds to wait before the next attempt, or None when the error should be raised."""
        level = getattr(error, "log_level", logging.WARNING)
        if not self._will_retry(error, attempt):
            logger.log(level, "%s failed on attempt %d: %r", self._route_name, attempt, error)
            return None
        delay = self._delay(error, attempt)
        logger.log(
            level,
            "%s failed on attempt %d of %d: %r; retrying in %.2fs",
            self._route_name,
            attempt,
            self._retries.attempts,
            error,
            delay,
        )
        return delay

    def _will_retry(self, error: Exception, attempt: int) -> bool:
        return attempt < self._retries.attempts and self._should_retry(error, attempt)

    def _delay(self, error: Exception, attempt: int) -> float:
        """The backoff delay, lengthened to a longer Retry-After. Retry-After is the least the
        server asks for, so it never shortens the backoff: some APIs answer a 429 with
        Retry-After: 0."""
        backoff = self._retries.delay(attempt)
        retry_after = _retry_after_seconds(error)
        if retry_after is None:
            return backoff
        return self._retries.capped(max(retry_after, backoff))


def _retry_after_seconds(error: Exception) -> float | None:
    if not isinstance(error, UnexpectedResponse):
        return None
    header = error.response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
