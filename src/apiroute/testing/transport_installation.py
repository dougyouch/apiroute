from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from apiroute.transport_configuration import ASYNC_TRANSPORTS, TRANSPORTS


@contextmanager
def installed(transport: Any, async_transport: Any) -> Iterator[None]:
    """Makes every client send through these transports inside the block, replacing the process
    default and every per-class registration, which come back on exit. A client given its own
    transport= or async_transport= argument keeps it."""
    saved = TRANSPORTS.snapshot(), ASYNC_TRANSPORTS.snapshot()
    for registry, chosen in ((TRANSPORTS, transport), (ASYNC_TRANSPORTS, async_transport)):
        registry.reset()
        registry.use(chosen)
    try:
        yield
    finally:
        TRANSPORTS.restore(saved[0])
        ASYNC_TRANSPORTS.restore(saved[1])
