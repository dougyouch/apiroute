import inspect
from collections.abc import Callable
from typing import Any

from apiroute.from_client import FROM_CLIENT
from apiroute.http_method import infer_http_method, normalize_http_method
from apiroute.path_template import PathTemplate
from apiroute.route_compiler import STREAM_PARAMS
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.route_spec import RouteSpec
from apiroute.value_template import ValueTemplate

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY


class GeneratedSignature:
    """Builds the stub function for a route written without a def.

    Every placeholder becomes a keyword-only parameter, in path, query, body order. One the
    class declares (a class attribute, method, property or annotation such as `org: str`)
    is optional and falls back to the client's value. A POST, PUT or PATCH route without a
    body template also takes an optional `body`, and a stream="file" or "io" route a
    required `file` or `io`.
    """

    def __init__(self, owner: type, name: str, spec: RouteSpec):
        self._owner = owner
        self._name = name
        self._spec = spec

    def function(self) -> Callable:
        try:
            signature = self._signature()
        except (TypeError, ValueError) as error:
            raise RouteDefinitionError(f"{self._label()}: {error}") from error
        return self._stub(signature)

    def _signature(self) -> inspect.Signature:
        parameters = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        parameters += [self._parameter(name) for name in self._placeholder_names()]
        if self._takes_body():
            parameters.append(inspect.Parameter("body", _KEYWORD_ONLY, default=None))
        stream_param = STREAM_PARAMS.get(self._spec.stream)
        if stream_param is not None:
            parameters.append(inspect.Parameter(stream_param, _KEYWORD_ONLY))
        return inspect.Signature(parameters)

    def _placeholder_names(self) -> list[str]:
        names = list(PathTemplate(self._spec.path).names)
        for template in (self._spec.query, self._spec.body, self._spec.headers):
            if template is not None and not isinstance(template, (str, bytes)):
                names += ValueTemplate(template).names
        return list(dict.fromkeys(names))

    def _parameter(self, name: str) -> inspect.Parameter:
        if self._declared_on_class(name):
            return inspect.Parameter(name, _KEYWORD_ONLY, default=FROM_CLIENT)
        return inspect.Parameter(name, _KEYWORD_ONLY)

    def _declared_on_class(self, name: str) -> bool:
        return hasattr(self._owner, name) or any(
            name in _annotations(base) for base in self._owner.__mro__
        )

    def _takes_body(self) -> bool:
        if self._spec.body is not None:
            return False
        method = self._spec.method
        http_method = infer_http_method(self._name) if method is None else method
        return normalize_http_method(http_method) in _BODY_METHODS

    def _stub(self, signature: inspect.Signature) -> Callable:
        def stub(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("generated routes are called through the client")

        stub.__name__ = self._name
        stub.__qualname__ = self._label()
        stub.__module__ = self._owner.__module__
        stub.__doc__ = f"{self._spec.method or infer_http_method(self._name)} {self._spec.path}"
        stub.__signature__ = signature
        return stub

    def _label(self) -> str:
        return f"{self._owner.__qualname__}.{self._name}"


def _annotations(cls: type) -> dict[str, Any]:
    """A class's own annotations; ones that can't be evaluated still count by name."""
    try:
        return inspect.get_annotations(cls)
    except Exception:
        return vars(cls).get("__annotations__", {})
