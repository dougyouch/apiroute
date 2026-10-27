import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any


class RetrySleeper:
    """How every client waits between retry attempts: time.sleep and asyncio.sleep unless
    replaced, e.g. by apiroute.testing to record the waits instead of sleeping."""

    def __init__(self):
        self.reset()

    def sleep(self, seconds: float) -> None:
        self._sleep(seconds)

    async def async_sleep(self, seconds: float) -> None:
        await self._async_sleep(seconds)

    def replace(
        self, sleep: Callable[[float], Any], async_sleep: Callable[[float], Awaitable[Any]]
    ) -> None:
        self._sleep = sleep
        self._async_sleep = async_sleep

    def current(self) -> tuple[Callable[[float], Any], Callable[[float], Awaitable[Any]]]:
        """The sleep functions in use, to hand back to replace()."""
        return self._sleep, self._async_sleep

    def reset(self) -> None:
        self.replace(time.sleep, asyncio.sleep)


# The process-wide sleeper every Client retries with
RETRY_SLEEPER = RetrySleeper()
