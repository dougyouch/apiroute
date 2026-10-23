from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from apiroute.retry_policy import RetryPolicy

T = TypeVar("T")


class AsyncRetryRunner:
    """The async retry loop: awaits each attempt and sleeps without blocking the event loop."""

    def __init__(self, policy: RetryPolicy, sleep: Callable[[float], Awaitable[Any]]):
        self._policy = policy
        self._sleep = sleep

    async def run(self, attempt: Callable[[], Awaitable[T]]) -> T:
        number = 1
        while True:
            try:
                return await attempt()
            except Exception as error:
                delay = self._policy.delay_before_retry(error, number)
                if delay is None:
                    raise
            await self._sleep(delay)
            number += 1
