from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.telemetry.open_telemetry import OpenTelemetry


class TracedTransport:
    """Sends each request inside a span, with the trace context in its headers."""

    def __init__(self, inner: Any, telemetry: OpenTelemetry, redact_url: Callable[[str], str]):
        self._inner = inner
        self._telemetry = telemetry
        self._redact_url = redact_url

    def send(self, spec: RequestSpec) -> httpx.Response:
        with self._telemetry.span(spec, self._redact_url) as span:
            response = self._inner.send(span.inject(spec))
            span.record(response)
            return response

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        return self._stream(spec)

    @contextmanager
    def _stream(self, spec: RequestSpec) -> Iterator[httpx.Response]:
        """The span ends once the status is in, since the body may take hours."""
        with ExitStack() as opening:  # closes the stream if opening it fails
            with self._telemetry.span(spec, self._redact_url) as span:
                response = opening.enter_context(self._inner.stream(span.inject(spec)))
                span.record(response)
            opened = opening.pop_all()
        with opened:
            yield response
