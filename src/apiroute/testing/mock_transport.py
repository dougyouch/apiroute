import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.testing.async_mock_transport import AsyncMockTransport
from apiroute.testing.mock_call import MockCall
from apiroute.testing.mock_route import MockRoute
from apiroute.testing.response_source import ResponseSource, produce_response
from apiroute.testing.unmatched_request import UnmatchedRequest
from apiroute.transports.httpx_client_transport import request_arguments


class MockTransport:
    """A transport that answers from the test instead of the network, and records every call.

    A request is answered by the first matching route (on()), else the next queued response
    (respond()), else handler, else it raises UnmatchedRequest. Requests are encoded by httpx
    through an httpx.MockTransport, so a call's .request is what would have been sent.

    mock.aio is the async side, sharing the same routes, queue and calls:
    Client(transport=mock, async_transport=mock.aio), or install both with mock_transport().
    """

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response] | None = None):
        self.calls: list[MockCall] = []
        # Retry waits recorded while mock_transport() has this mock installed
        self.sleeps: list[float] = []
        self.aio = AsyncMockTransport(self)
        self._handler = handler
        self._routes: list[MockRoute] = []
        self._queue: list[ResponseSource] = []
        self._lock = threading.Lock()

    def on(
        self,
        *,
        operation: str | None = None,
        method: str | None = None,
        path: str | None = None,
        where: Callable[[MockCall], bool] | None = None,
    ) -> MockRoute:
        """A route answering matching requests; give it responses with .respond()."""
        route = MockRoute(operation, method, path, where)
        self._routes.append(route)
        return route

    def respond(self, *responses: ResponseSource) -> "MockTransport":
        """Queues responses, each answering one request no route matches, in order."""
        self._queue.extend(responses)
        return self

    @property
    def last(self) -> MockCall:
        return self.calls[-1]

    @property
    def pending(self) -> list[ResponseSource]:
        """Queued responses no request has used yet."""
        return list(self._queue)

    def send(self, spec: RequestSpec) -> httpx.Response:
        with self._http_client(spec) as client:
            return client.request(spec.method, spec.url, **request_arguments(spec))

    @contextmanager
    def stream(self, spec: RequestSpec) -> Iterator[httpx.Response]:
        with self._http_client(spec) as client:
            with client.stream(spec.method, spec.url, **request_arguments(spec)) as response:
                yield response

    def close(self) -> None:
        pass

    def answer(self, spec: RequestSpec, request: httpx.Request) -> httpx.Response:
        """The response for one request, recording it as a call."""
        call = MockCall(spec, request)
        with self._lock:
            self.calls.append(call)
            source = self._source_for(call)
        return produce_response(source, request)

    def _source_for(self, call: MockCall) -> ResponseSource:
        for route in self._routes:
            if route.matches(call):
                return route.take(call)
        if self._queue:
            return self._queue.pop(0)
        if self._handler is not None:
            return self._handler
        raise UnmatchedRequest(call)

    def _http_client(self, spec: RequestSpec) -> httpx.Client:
        return httpx.Client(transport=self._handler_for(spec), trust_env=False)

    def _handler_for(self, spec: RequestSpec) -> httpx.MockTransport:
        return httpx.MockTransport(lambda request: self.answer(spec, request))
