import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

import httpx

from apiroute.async_retry_runner import AsyncRetryRunner
from apiroute.client_config import ClientConfig
from apiroute.idempotency_key import IdempotencyKey
from apiroute.request_builder import RequestBuilder
from apiroute.request_options import RequestOptions
from apiroute.request_spec import RequestSpec
from apiroute.response_reader import ResponseReader
from apiroute.retries import Retries
from apiroute.retry_policy import RetryPolicy
from apiroute.retry_runner import RetryRunner
from apiroute.route_definition import RouteDefinition
from apiroute.stream_reader import StreamReader
from apiroute.streaming.async_stream_reconnector import AsyncStreamReconnector
from apiroute.streaming.stream_decoders import RECONNECTING_STREAMS
from apiroute.streaming.stream_reconnector import StreamReconnector
from apiroute.unsent_retry_filter import UnsentRetryFilter


class RouteExecutor:
    """Runs one route call: build the request, then send and read it inside the retry loop.

    execute and execute_async share every step but the send and the sleep.
    """

    def __init__(self, router: Any, definition: RouteDefinition, options: RequestOptions):
        self._router = router
        self._root = router._root
        self._definition = definition
        self._options = options

    def execute(self, values: Mapping[str, Any]) -> Any:
        spec, policy = self._prepare(values)
        transport = self._root._http_transport()
        runner = RetryRunner(policy, self._root._sleep)
        if self._definition.stream is None:
            return runner.run(lambda: self._read(self._send(transport, spec)))
        # Only opening the stream is retried; once the body starts, a failure is raised (or,
        # for an event stream, reconnected as the policy allows)
        stream = self._stream_reader(values)

        def open_stream(resume_headers: dict[str, str]) -> Any:
            request = _with_headers(spec, resume_headers)
            return runner.run(lambda: self._open(stream, transport, request))

        response, stack = open_stream({})
        reconnector = None
        if self._definition.stream in RECONNECTING_STREAMS:
            reconnector = StreamReconnector(policy, self._root._sleep, open_stream)
        return stream.consume(response, stack, reconnector)

    async def execute_async(self, values: Mapping[str, Any]) -> Any:
        spec, policy = self._prepare(values)
        transport = self._root._async_http_transport()
        runner = AsyncRetryRunner(policy, self._root._async_sleep)
        if self._definition.stream is None:

            async def attempt() -> Any:
                hooked = self._before(spec)
                started = time.perf_counter()
                return self._read(self._after(hooked, await transport.send(hooked), started))

            return await runner.run(attempt)
        stream = self._stream_reader(values)

        async def open_stream(resume_headers: dict[str, str]) -> Any:
            request = _with_headers(spec, resume_headers)

            async def open_once() -> Any:
                hooked = self._before(request)
                started = time.perf_counter()
                opened = await stream.open_async(transport, hooked)
                self._after(hooked, opened[0], started)
                return opened

            return await runner.run(open_once)

        response, stack = await open_stream({})
        reconnector = None
        if self._definition.stream in RECONNECTING_STREAMS:
            reconnector = AsyncStreamReconnector(policy, self._root._async_sleep, open_stream)
        return await stream.consume_async(response, stack, reconnector)

    def _prepare(self, values: Mapping[str, Any]) -> tuple[RequestSpec, RetryPolicy]:
        config = self._router._request_config()
        spec = RequestBuilder(config, self._root, self._options).build(self._definition, values)
        should_retry = self._should_retry(config, spec)
        policy = RetryPolicy(self._retries(config), should_retry, self._definition.name)
        return spec, policy

    def _should_retry(
        self, config: ClientConfig, spec: RequestSpec
    ) -> Callable[[Exception, int], bool]:
        """The client's should_retry; for a request that isn't idempotent (by the client's
        idempotent hook, else the route) and carries no idempotency key, without the errors
        that may follow sending."""
        definition = self._definition
        verdict = self._root.idempotent(spec)
        idempotent = definition.idempotent if verdict is None else verdict
        if idempotent or IdempotencyKey(definition, config).sent_in(spec.headers):
            return self._root.should_retry
        return UnsentRetryFilter(self._root.should_retry)

    def _read(self, response: httpx.Response) -> Any:
        return self._response_reader().read(response)

    def _response_reader(self) -> ResponseReader:
        definition = self._definition
        returns = self._options.returns or definition.returns
        return ResponseReader(
            definition.name,
            definition.expected,
            returns,
            definition.converter,
            definition.decoder,
            definition.check,
            redact_url=self._root.redact_url,
        )

    def _stream_reader(self, values: Mapping[str, Any]) -> StreamReader:
        destination = values.get(self._definition.stream_param)
        definition = self._definition
        return StreamReader(
            self._response_reader(), definition.stream, destination, definition.converter
        )

    def _send(self, transport: Any, spec: RequestSpec) -> httpx.Response:
        hooked = self._before(spec)
        started = time.perf_counter()
        return self._after(hooked, transport.send(hooked), started)

    def _open(self, stream: StreamReader, transport: Any, spec: RequestSpec) -> Any:
        hooked = self._before(spec)
        started = time.perf_counter()
        opened = stream.open(transport, hooked)
        self._after(hooked, opened[0], started)
        return opened

    def _before(self, spec: RequestSpec) -> RequestSpec:
        """Runs the client's on_request, which may return a changed request (e.g. signed)."""
        return self._root.on_request(spec) or spec

    def _after(self, spec: RequestSpec, response: httpx.Response, started: float) -> Any:
        self._root.last_response = response
        self._root.on_response(spec, response, time.perf_counter() - started)
        self._root.check_response(spec, response)
        return response

    def _retries(self, config: ClientConfig) -> Retries:
        retries = self._options.retries
        if retries is None:
            return config.retries
        if isinstance(retries, int):
            return replace(config.retries, attempts=retries)
        return retries


def _with_headers(spec: RequestSpec, headers: dict[str, str]) -> RequestSpec:
    """The request with these headers added, e.g. Last-Event-ID when a stream resumes."""
    return replace(spec, headers={**spec.headers, **headers}) if headers else spec
