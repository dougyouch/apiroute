import inspect
import threading
from typing import Any

import httpx

from apiroute.lazy_attribute import LazyAttribute
from apiroute.route_method import RouteMethod
from apiroute.section_accessor import SectionAccessor
from apiroute.testing.mock_call import MockCall
from apiroute.testing.mock_response_mismatch import MockResponseMismatch
from apiroute.typed_client import TypedClient, _adapter, _resolved


class ResponseSchemas:
    """The response models a generated client's .models layer declares, by operation, for
    checking that test mocks still look like the API (it needs pydantic):

        with mock_transport(check=ResponseSchemas(GitHubApi)) as mock:
            mock.on(operation="repos/get").respond(httpx.Response(200, json={"name": "x"}))
            ...  # MockResponseMismatch: the mocked repository lacks required fields

    A MockTransport, mock_transport() or cassette() given it as check= validates every 2xx
    JSON response to a known operation against the operation's response model, and raises
    MockResponseMismatch (an AssertionError) when it doesn't fit. Responses to operations the
    client doesn't declare, and those without a model, pass unchecked.

    The client class (a generated one, or your subclass of one) is walked once, on first use:
    every section and its .models view is imported then.
    """

    def __init__(self, client_class: type):
        self._client_class = client_class
        self._models: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def model_for(self, operation: str) -> Any:
        """The response type declared for an operation (its spec's operationId), or None."""
        with self._lock:
            if self._models is None:
                self._models = {}
                self._collect(self._client_class, set())
        return self._models.get(operation)

    def verify(self, call: MockCall, response: httpx.Response) -> None:
        if not response.is_success or "json" not in response.headers.get("content-type", ""):
            return
        model = self.model_for(call.operation)
        if model is None:
            return
        response.read()
        try:
            _adapter(model).validate_python(response.json())
        except Exception as error:
            raise MockResponseMismatch(
                f"{call.describe()}: the response doesn't fit the spec's {_name(model)}:\n{error}"
            ) from error

    def _collect(self, router_class: type, seen: set[type]) -> None:
        if router_class in seen:
            return
        seen.add(router_class)
        routes: dict[str, RouteMethod] = {}
        typed: type | None = None
        for name in dir(router_class):
            attribute = inspect.getattr_static(router_class, name, None)
            if isinstance(attribute, RouteMethod):
                routes[name] = attribute
            elif isinstance(attribute, SectionAccessor):
                self._collect(attribute.section_class, seen)
            elif isinstance(attribute, LazyAttribute):
                loaded = attribute.load()
                if issubclass(loaded, TypedClient):
                    typed = loaded
                else:
                    self._collect(loaded, seen)
        if typed is not None:
            self._declare(routes, typed)

    def _declare(self, routes: dict[str, RouteMethod], typed: type) -> None:
        assert self._models is not None
        for name, route in routes.items():
            definition = route.definition
            method = getattr(typed, name, None)
            returns = getattr(method, "__annotations__", {}).get("return")
            if definition.paginate is not None or returns in (None, "None"):
                continue
            model = _resolved(typed.__module__, returns) if isinstance(returns, str) else returns
            self._models.setdefault(definition.operation or name, model)


def _name(model: Any) -> str:
    return getattr(model, "__name__", None) or str(model)
