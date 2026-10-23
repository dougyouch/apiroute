import logging
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

from apiroute.retries import Retries
from apiroute.unexpected_response import UnexpectedResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryRunner:
    """Runs one request attempt after another until it succeeds or retrying stops."""

    def __init__(
        self,
        retries: Retries,
        should_retry: Callable[[Exception, int], bool],
        sleep: Callable[[float], Any],
    ):
        self._retries = retries
        self._should_retry = should_retry
        self._sleep = sleep

    def run(self, attempt: Callable[[], T], route_name: str) -> T:
        number = 1
        while True:
            try:
                return attempt()
            except Exception as error:
                if not self._will_retry(error, number):
                    logger.warning("%s failed on attempt %d: %r", route_name, number, error)
                    raise
                delay = self._delay(error, number)
                logger.warning(
                    "%s failed on attempt %d of %d: %r; retrying in %.2fs",
                    route_name,
                    number,
                    self._retries.attempts,
                    error,
                    delay,
                )
            self._sleep(delay)
            number += 1

    def _will_retry(self, error: Exception, number: int) -> bool:
        return number < self._retries.attempts and self._should_retry(error, number)

    def _delay(self, error: Exception, number: int) -> float:
        retry_after = _retry_after_seconds(error)
        if retry_after is None:
            return self._retries.delay(number)
        return self._retries.capped(retry_after)


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
