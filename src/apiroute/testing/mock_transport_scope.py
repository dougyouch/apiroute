from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from apiroute.testing.mock_transport import MockTransport
from apiroute.testing.sleep_recording import recorded_sleeps
from apiroute.testing.transport_installation import installed


@contextmanager
def mock_transport(
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
    *,
    assert_all_used: bool = True,
    check: Any = None,
) -> Iterator[MockTransport]:
    """Sends every client's requests, sync and async, to a new MockTransport inside the block.

    It replaces the process default and every per-class registration, which come back on exit.
    A client given its own transport= or async_transport= argument keeps it. Retries don't
    wait: their waits are recorded in mock.sleeps. With assert_all_used, a block that ends
    normally with queued responses still unused fails. check, a ResponseSchemas, validates each
    JSON response against the model its operation's spec declares.
    """
    mock = MockTransport(handler, check=check)
    with installed(mock, mock.aio), recorded_sleeps(mock.sleeps):
        yield mock
    if assert_all_used and mock.pending:
        raise AssertionError(f"{len(mock.pending)} queued mock responses were never requested")
