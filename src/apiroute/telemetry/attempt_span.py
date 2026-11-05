from dataclasses import replace
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec

_ERROR_STATUS = 400


class AttemptSpan:
    """The span of one request attempt: carries its trace context to the server and records
    the response's status, as OpenTelemetry's HTTP client conventions say."""

    def __init__(self, span: Any, propagator: Any, status: Any):
        self._span = span
        self._propagator = propagator
        self._status = status  # opentelemetry.trace.Status and StatusCode, imported lazily

    def inject(self, spec: RequestSpec) -> RequestSpec:
        """The request carrying the trace context (traceparent), when propagation is on."""
        if self._propagator is None:
            return spec
        carrier: dict[str, str] = {}
        self._propagator.inject(carrier)
        return replace(spec, headers={**spec.headers, **carrier}) if carrier else spec

    def record(self, response: httpx.Response) -> None:
        self._span.set_attribute("http.response.status_code", response.status_code)
        if response.status_code >= _ERROR_STATUS:
            self._span.set_attribute("error.type", str(response.status_code))
            status, code = self._status
            self._span.set_status(status(code.ERROR))

    def fail(self, error: BaseException) -> None:
        self._span.set_attribute("error.type", type(error).__qualname__)
