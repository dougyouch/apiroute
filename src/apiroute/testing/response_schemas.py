import inspect
import threading
from typing import Any

import httpx

from apiroute.call_context import CallContext
from apiroute.lazy_attribute import LazyAttribute
from apiroute.testing.mock_call import MockCall
from apiroute.testing.mock_response_mismatch import MockResponseMismatch
from apiroute.typed_client import TypedClient, _adapter, _resolved

_UNKNOWN = object()


class ResponseSchemas:
    """Checks that test mocks still look like the API, using the response models a generated
    client's .models layer declares (it needs pydantic):

        with mock_transport(check=ResponseSchemas(GitHubApi)) as mock:
            mock.on(operation="repos/get").respond(httpx.Response(200, json={"name": "x"}))
            ...  # MockResponseMismatch: the mocked repository lacks required fields

    A MockTransport, mock_transport() or cassette() given it as check= validates every 2xx
    JSON response to a call made through client_class (or a subclass) against the model the
    route's .models method returns, and raises MockResponseMismatch (an AssertionError) when
    it doesn't fit. Routes without a .models method or a model pass unchecked, as do paginated
    and poll= routes, whose responses are pages and status bodies rather than the model.

    Nothing is loaded up front: a checked call imports only its own section's .models view
    and the model that route returns, as making the typed call would, so a client with
    thousands of operations stays as light in tests as in production.
    """

    def __init__(self, client_class: type):
        self._client_class = client_class
        self._models: dict[tuple[type, str], Any] = {}
        self._lock = threading.Lock()

    def model_for(self, router_class: type, route_name: str) -> Any:
        """The response type the route's .models method declares, or None."""
        key = (router_class, route_name)
        with self._lock:
            model = self._models.get(key, _UNKNOWN)
            if model is _UNKNOWN:
                model = self._models[key] = _declared(router_class, route_name)
        return model

    def verify(self, call: MockCall, response: httpx.Response) -> None:
        context = CallContext.current()
        if context is None or not self._checks(context, call, response):
            return
        model = self.model_for(type(context.router), context.definition.name)
        if model is None:
            return
        response.read()
        try:
            _adapter(model).validate_python(response.json())
        except Exception as error:
            raise MockResponseMismatch(
                f"{call.describe()}: the response doesn't fit the spec's {_name(model)}:\n{error}"
            ) from error

    def _checks(self, context: CallContext, call: MockCall, response: httpx.Response) -> bool:
        definition = context.definition
        return (
            isinstance(context.router._root, self._client_class)
            and call.operation == (definition.operation or definition.name)
            and definition.paginate is None
            and definition.poll is None
            and response.is_success
            and "json" in response.headers.get("content-type", "")
        )


def _declared(router_class: type, route_name: str) -> Any:
    """The return type of route_name on router_class's .models view, imported only now."""
    typed = _models_view(router_class)
    method = getattr(typed, route_name, None) if typed is not None else None
    returns = getattr(method, "__annotations__", {}).get("return")
    if returns in (None, "None"):
        return None
    assert typed is not None
    return _resolved(typed.__module__, returns) if isinstance(returns, str) else returns


def _models_view(router_class: type) -> type | None:
    attribute = inspect.getattr_static(router_class, "models", None)
    if isinstance(attribute, LazyAttribute):
        attribute = attribute.load()
    if isinstance(attribute, type) and issubclass(attribute, TypedClient):
        return attribute
    return None


def _name(model: Any) -> str:
    return getattr(model, "__name__", None) or str(model)
