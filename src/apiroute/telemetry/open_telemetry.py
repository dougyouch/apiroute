from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from apiroute.full_url import full_url
from apiroute.request_spec import RequestSpec
from apiroute.telemetry.attempt_span import AttemptSpan


class OpenTelemetry:
    """Traces every request attempt as an OpenTelemetry client span. Set one as a client's
    `telemetry` (it needs the otel extra: pip install 'apiroute[otel]'):

        class GitHub(Client):
            telemetry = OpenTelemetry()

    Each attempt (retries, pages and stream reconnects included) is a span named after the
    request's operation (the route's operation=, an OpenAPI operationId or the method name),
    with the HTTP client attributes: http.request.method, url.full (as redact_url shows it),
    server.address, server.port, http.response.status_code, and error.type for a 4xx or 5xx
    status or an exception, which also mark the span as an error. A stream's span ends once
    its status is in. Spans come from the global tracer provider unless tracer_provider is
    given, and the trace context is sent with each request (traceparent) unless
    propagate=False.
    """

    def __init__(self, tracer_provider: Any = None, *, propagate: bool = True):
        try:
            from opentelemetry import propagate as propagation
            from opentelemetry import trace
        except ImportError as error:  # an optional dependency, imported only when used
            raise ImportError(
                "OpenTelemetry needs opentelemetry-api: pip install 'apiroute[otel]'"
            ) from error
        self._tracer = trace.get_tracer("apiroute", tracer_provider=tracer_provider)
        self._client_kind = trace.SpanKind.CLIENT
        self._status = (trace.Status, trace.StatusCode)
        self._propagator = propagation if propagate else None

    @contextmanager
    def span(self, spec: RequestSpec, redact_url: Callable[[str], str]) -> Iterator[AttemptSpan]:
        url = full_url(spec)
        attributes: dict[str, Any] = {
            "http.request.method": spec.method,
            "url.full": redact_url(str(url)),
            "server.address": url.host,
            "server.port": url.port or (443 if url.scheme == "https" else 80),
        }
        if spec.operation:
            attributes["apiroute.operation"] = spec.operation
        with self._tracer.start_as_current_span(
            spec.operation or spec.method, kind=self._client_kind, attributes=attributes
        ) as span:
            attempt = AttemptSpan(span, self._propagator, self._status)
            try:
                yield attempt
            except BaseException as error:
                attempt.fail(error)
                raise
