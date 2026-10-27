import copy
from collections.abc import Callable

import httpx

# What a test answers a request with: a response, an exception to raise, or a function of the
# request returning a response (an httpx.MockTransport handler)
ResponseSource = httpx.Response | Exception | Callable[[httpx.Request], httpx.Response]


def produce_response(source: ResponseSource, request: httpx.Request) -> httpx.Response:
    """The response source gives for request, raising it when it is an exception."""
    if isinstance(source, Exception):
        raise _attached(source, request)
    if isinstance(source, httpx.Response):
        return _fresh(source)
    return source(request)


def _attached(error: Exception, request: httpx.Request) -> Exception:
    """httpx's errors carry their request; one built in a test usually has none yet."""
    if isinstance(error, httpx.RequestError):
        try:
            _ = error.request
        except RuntimeError:
            error.request = request
    return error


def _fresh(response: httpx.Response) -> httpx.Response:
    """A copy of a read response, so a response answered twice gets its own .request each time.
    One with an unread stream can only be answered once and is returned as is."""
    try:
        _ = response.content
    except httpx.ResponseNotRead:
        return response
    fresh = copy.copy(response)
    fresh.headers = response.headers.copy()
    return fresh
