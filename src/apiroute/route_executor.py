import time
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import httpx

from apiroute.async_retry_runner import AsyncRetryRunner
from apiroute.client_config import ClientConfig
from apiroute.request_builder import RequestBuilder
from apiroute.request_options import RequestOptions
from apiroute.request_spec import RequestSpec
from apiroute.response_reader import ResponseReader
from apiroute.retries import Retries
from apiroute.retry_policy import RetryPolicy
from apiroute.retry_runner import RetryRunner
from apiroute.route_definition import RouteDefinition
from apiroute.stream_reader import StreamReader


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
        # Only opening the stream is retried; once the body starts, a failure is raised
        stream = self._stream_reader(values)
        response, stack = runner.run(lambda: self._open(stream, transport, spec))
        return stream.consume(response, stack)

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

        async def open_stream() -> Any:
            hooked = self._before(spec)
            started = time.perf_counter()
            opened = await stream.open_async(transport, hooked)
            self._after(hooked, opened[0], started)
            return opened

        response, stack = await runner.run(open_stream)
        return await stream.consume_async(response, stack)

    def _prepare(self, values: Mapping[str, Any]) -> tuple[RequestSpec, RetryPolicy]:
        config = self._router._request_config()
        spec = RequestBuilder(config, self._root, self._options).build(self._definition, values)
        policy = RetryPolicy(self._retries(config), self._root.should_retry, self._definition.name)
        return spec, policy

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
            redact_url=self._root.redact_url,
        )

    def _stream_reader(self, values: Mapping[str, Any]) -> StreamReader:
        destination = values.get(self._definition.stream_param)
        return StreamReader(self._response_reader(), self._definition.stream, destination)

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
        return response

    def _retries(self, config: ClientConfig) -> Retries:
        retries = self._options.retries
        if retries is None:
            return config.retries
        if isinstance(retries, int):
            return replace(config.retries, attempts=retries)
        return retries
