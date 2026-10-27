from collections.abc import Iterator
from contextlib import contextmanager

from apiroute.retry_sleeper import RETRY_SLEEPER


@contextmanager
def recorded_sleeps(sleeps: list[float] | None = None) -> Iterator[list[float]]:
    """Retries don't wait inside the block: each wait's seconds are appended to the list
    yielded (sleeps, if given) instead. The previous sleep functions come back on exit."""
    recorded = [] if sleeps is None else sleeps

    async def async_sleep(seconds: float) -> None:
        recorded.append(seconds)

    previous = RETRY_SLEEPER.current()
    RETRY_SLEEPER.replace(recorded.append, async_sleep)
    try:
        yield recorded
    finally:
        RETRY_SLEEPER.replace(*previous)
