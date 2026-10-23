from collections.abc import Callable
from typing import Any, TypeVar

from apiroute.retry_policy import RetryPolicy

T = TypeVar("T")


class RetryRunner:
    """Runs one request attempt after another until it succeeds or the policy says stop."""

    def __init__(self, policy: RetryPolicy, sleep: Callable[[float], Any]):
        self._policy = policy
        self._sleep = sleep

    def run(self, attempt: Callable[[], T]) -> T:
        number = 1
        while True:
            try:
                return attempt()
            except Exception as error:
                delay = self._policy.delay_before_retry(error, number)
                if delay is None:
                    raise
            self._sleep(delay)
            number += 1
