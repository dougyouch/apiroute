from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, NoReturn

import httpx


class NetworkBlocked(AssertionError):
    """A request reached httpx's real network transport while block_network() was active."""


@contextmanager
def block_network() -> Iterator[None]:
    """Inside the block, any request that reaches httpx's real network transports raises
    NetworkBlocked instead of connecting: whatever transport a client uses, a test can't
    reach a real API by accident. httpx.MockTransport and MockTransport are unaffected."""
    sync_send = httpx.HTTPTransport.handle_request
    async_send = httpx.AsyncHTTPTransport.handle_async_request
    httpx.HTTPTransport.handle_request = _refuse
    httpx.AsyncHTTPTransport.handle_async_request = _refuse_async
    try:
        yield
    finally:
        httpx.HTTPTransport.handle_request = sync_send
        httpx.AsyncHTTPTransport.handle_async_request = async_send


def _refuse(transport: Any, request: httpx.Request) -> NoReturn:
    raise NetworkBlocked(f"a test made a real network request: {request.method} {request.url}")


async def _refuse_async(transport: Any, request: httpx.Request) -> NoReturn:
    _refuse(transport, request)
