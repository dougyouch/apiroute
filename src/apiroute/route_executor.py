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
            return runner.run(lambda: self._read(transport.send(spec)))
        # Only opening the stream is retried; once the body starts, a failure is raised
        stream = self._stream_reader(values)
        response, stack = runner.run(lambda: self._opened(stream.open(transport, spec)))
        return stream.consume(response, stack)

    async def execute_async(self, values: Mapping[str, Any]) -> Any:
        spec, policy = self._prepare(values)
        transport = self._root._async_http_transport()
        runner = AsyncRetryRunner(policy, self._root._async_sleep)
        if self._definition.stream is None:

            async def attempt() -> Any:
                return self._read(await transport.send(spec))

            return await runner.run(attempt)
        stream = self._stream_reader(values)

        async def open_stream() -> Any:
            return self._opened(await stream.open_async(transport, spec))

        response, stack = await runner.run(open_stream)
        return await stream.consume_async(response, stack)

    def _prepare(self, values: Mapping[str, Any]) -> tuple[RequestSpec, RetryPolicy]:
        config = self._router._request_config()
        spec = RequestBuilder(config, self._root, self._options).build(self._definition, values)
        policy = RetryPolicy(self._retries(config), self._root.should_retry, self._definition.name)
        return spec, policy

    def _read(self, response: httpx.Response) -> Any:
        self._root.last_response = response
        return self._response_reader().read(response)

    def _response_reader(self) -> ResponseReader:
        returns = self._options.returns or self._definition.returns
        return ResponseReader(self._definition.name, self._definition.expected, returns)

    def _stream_reader(self, values: Mapping[str, Any]) -> StreamReader:
        destination = values.get(self._definition.stream_param)
        return StreamReader(self._response_reader(), self._definition.stream, destination)

    def _opened(self, opened: tuple[httpx.Response, Any]) -> tuple[httpx.Response, Any]:
        self._root.last_response = opened[0]
        return opened

    def _retries(self, config: ClientConfig) -> Retries:
        retries = self._options.retries
        if retries is None:
            return config.retries
        if isinstance(retries, int):
            return replace(config.retries, attempts=retries)
        return retries
