from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from apiroute.client_config import ClientConfig
from apiroute.request_builder import RequestBuilder
from apiroute.request_options import RequestOptions
from apiroute.request_spec import RequestSpec
from apiroute.response_reader import ResponseReader
from apiroute.retries import Retries
from apiroute.retry_runner import RetryRunner
from apiroute.route_definition import RouteDefinition


class RouteExecutor:
    """Runs one route call: build the request, then send and read it inside the retry loop."""

    def __init__(self, router: Any, definition: RouteDefinition, options: RequestOptions):
        self._router = router
        self._root = router._root
        self._definition = definition
        self._options = options

    def execute(self, values: Mapping[str, Any]) -> Any:
        config = self._router._request_config()
        spec = RequestBuilder(config, self._root, self._options).build(self._definition, values)
        runner = RetryRunner(self._retries(config), self._root.should_retry, self._root._sleep)
        return runner.run(lambda: self._attempt(spec), self._definition.name)

    def _attempt(self, spec: RequestSpec) -> Any:
        response = self._root._http_transport().send(spec)
        self._root.last_response = response
        returns = self._options.returns or self._definition.returns
        return ResponseReader(self._definition.name, self._definition.expected, returns).read(
            response
        )

    def _retries(self, config: ClientConfig) -> Retries:
        retries = self._options.retries
        if retries is None:
            return config.retries
        if isinstance(retries, int):
            return replace(config.retries, attempts=retries)
        return retries
