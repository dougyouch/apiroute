from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx

from apiroute.testing.mock_transport import MockTransport
from apiroute.testing.sleep_recording import recorded_sleeps
from apiroute.transport_configuration import ASYNC_TRANSPORTS, TRANSPORTS


@contextmanager
def mock_transport(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    *,
    assert_all_used: bool = True,
) -> Iterator[MockTransport]:
    """Sends every client's requests, sync and async, to a new MockTransport inside the block.

    It replaces the process default and every per-class registration, which come back on exit.
    A client given its own transport= or async_transport= argument keeps it. Retries don't
    wait: their waits are recorded in mock.sleeps. With assert_all_used, a block that ends
    normally with queued responses still unused fails.
    """
    mock = MockTransport(handler)
    with _installed(mock), recorded_sleeps(mock.sleeps):
        yield mock
    if assert_all_used and mock.pending:
        raise AssertionError(f"{len(mock.pending)} queued mock responses were never requested")


@contextmanager
def _installed(mock: MockTransport) -> Iterator[None]:
    saved = TRANSPORTS.snapshot(), ASYNC_TRANSPORTS.snapshot()
    for registry, transport in ((TRANSPORTS, mock), (ASYNC_TRANSPORTS, mock.aio)):
        registry.reset()
        registry.use(transport)
    try:
        yield
    finally:
        TRANSPORTS.restore(saved[0])
        ASYNC_TRANSPORTS.restore(saved[1])
