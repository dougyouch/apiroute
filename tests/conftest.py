import json

import httpx
import pytest

from apiroute import AsyncHttpxClientTransport, HttpxClientTransport
from apiroute.transport_configuration import ASYNC_TRANSPORTS, TRANSPORTS


class Recorder:
    """A MockTransport handler that records requests and answers with queued responses."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self._responses: list = []

    def respond(self, *responses) -> "Recorder":
        self._responses.extend(responses)
        return self

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = self._responses.pop(0) if self._responses else httpx.Response(200, json={})
        if isinstance(response, Exception):
            raise response
        return response

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self):
        return json.loads(self.last.content)


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def transport(recorder) -> HttpxClientTransport:
    return HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder)))


@pytest.fixture
def async_transport(recorder) -> AsyncHttpxClientTransport:
    return AsyncHttpxClientTransport(httpx.AsyncClient(transport=httpx.MockTransport(recorder)))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_transports():
    yield
    TRANSPORTS.reset()
    ASYNC_TRANSPORTS.reset()
