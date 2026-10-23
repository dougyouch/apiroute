import inspect
from collections.abc import Callable
from typing import Annotated, Any, NamedTuple, get_origin

from apiroute.argument_targets import ArgumentTarget
from apiroute.deferred_converter import DeferredConverter
from apiroute.http_method import infer_http_method, normalize_http_method
from apiroute.model_types import strip_annotated
from apiroute.path_template import PathTemplate
from apiroute.request_options import RETURN_MODES
from apiroute.response_converter import converter_for
from apiroute.result import Result
from apiroute.route_definition import ArgumentBinding, RouteDefinition
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.route_spec import RouteSpec
from apiroute.value_template import ValueTemplate

_VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)

# Stream modes, and the parameter each takes its destination from
STREAM_PARAMS = {"file": "file", "io": "io", "iter": None}


class RouteCompiler:
    """Checks a @route against its method's signature and builds the RouteDefinition."""

    def __init__(self, owner_name: str, route_name: str, func: Callable, spec: RouteSpec):
        self._label = f"{owner_name}.{route_name}"
        self._name = route_name
        self._func = func
        self._spec = spec

    def compile(self) -> RouteDefinition:
        try:
            return self._compile()
        except (TypeError, ValueError) as error:
            raise RouteDefinitionError(f"{self._label}: {error}") from error

    def _compile(self) -> RouteDefinition:
        path = PathTemplate(self._path())
        query = None if self._spec.query is None else ValueTemplate(self._spec.query)
        body, literal_body = self._body()
        signature = inspect.signature(self._func)
        referenced = set(path.names) | _names(query) | _names(body)
        has_body_template = body is not None or literal_body is not None
        stream_param = self._stream_param(signature)
        bindings, body_param, result_param = self._bind_arguments(
            signature, referenced | {stream_param}, has_body_template
        )
        return RouteDefinition(
            name=self._name,
            http_method=self._http_method(),
            path=path,
            query=query,
            body=body,
            literal_body=literal_body,
            body_param=body_param,
            bindings=bindings,
            expected=self._expected(),
            returns=self._returns(),
            timeout=self._spec.timeout,
            signature=signature,
            result_param=result_param,
            stream=self._spec.stream,
            stream_param=stream_param,
            converter=self._converter(signature, result_param),
        )

    def _http_method(self) -> str:
        if self._spec.method is None:
            return infer_http_method(self._name)
        return normalize_http_method(self._spec.method)

    def _path(self) -> str:
        path = self._spec.path
        return path if path == "" or path.startswith("/") else f"/{path}"

    def _body(self) -> tuple[ValueTemplate | None, str | bytes | None]:
        body = self._spec.body
        if isinstance(body, (str, bytes)):
            return None, body
        return (None if body is None else ValueTemplate(body)), None

    def _bind_arguments(
        self, signature: inspect.Signature, referenced: set[str], has_body_template: bool
    ) -> tuple[tuple[ArgumentBinding, ...], str | None, str | None]:
        bindings: list[ArgumentBinding] = []
        body_param = None
        result_param = None
        for param in list(signature.parameters.values())[1:]:
            if param.kind in _VARIADIC:
                stars = "*" if param.kind is inspect.Parameter.VAR_POSITIONAL else "**"
                raise TypeError(f"{stars}{param.name} isn't supported; name each argument")
            markers = self._markers(param)
            target = next((m for m in map(_as_target, markers) if m is not None), None)
            if any(_is_result(marker) for marker in markers):
                result_param = self._only_result_param(result_param, param)
            elif target is not None and target.location == "body":
                body_param = self._only_body_param(body_param, param.name, has_body_template)
            elif target is not None:
                bindings.append(
                    ArgumentBinding(param.name, target.location, target.key_for(param.name))
                )
            elif param.name in referenced:
                continue
            elif param.name == "body" and not has_body_template:
                body_param = self._only_body_param(body_param, param.name, has_body_template)
            else:
                raise TypeError(
                    f"parameter {param.name!r} isn't used by the path, query or body; "
                    "annotate it with Query, Header or Body"
                )
        return tuple(bindings), body_param, result_param

    def _only_result_param(self, current: str | None, param: inspect.Parameter) -> str:
        if param.kind is not inspect.Parameter.KEYWORD_ONLY:
            raise TypeError(f"Result parameter {param.name!r} must be keyword-only (after *)")
        if current is not None:
            raise TypeError(f"both {current!r} and {param.name!r} are Result parameters")
        return param.name

    def _only_body_param(self, current: str | None, name: str, has_body_template: bool) -> str:
        if has_body_template:
            raise TypeError(f"parameter {name!r} is a body, but the route has a body template")
        if current is not None:
            raise TypeError(f"both {current!r} and {name!r} are bodies")
        return name

    def _markers(self, param: inspect.Parameter) -> tuple[Any, ...]:
        """The annotation, or with Annotated[...] its metadata, where Query, Header, Body or
        Result may be found."""
        annotation = self._evaluated(param.annotation)
        if get_origin(annotation) is Annotated:
            return annotation.__metadata__
        return (annotation,)

    def _evaluated(self, annotation: Any) -> Any:
        """String annotations (from __future__ import annotations) are evaluated when possible;
        one that names something not defined yet can't hold a Query, Header or Body anyway."""
        if not isinstance(annotation, str):
            return annotation
        try:
            return eval(annotation, getattr(self._func, "__globals__", {}))  # noqa: S307
        except Exception:
            return None

    def _stream_param(self, signature: inspect.Signature) -> str | None:
        if self._spec.stream is None:
            return None
        if self._spec.stream not in STREAM_PARAMS:
            raise ValueError(f"stream must be one of {tuple(STREAM_PARAMS)}")
        name = STREAM_PARAMS[self._spec.stream]
        if name is not None and name not in signature.parameters:
            raise TypeError(f"stream={self._spec.stream!r} needs a {name!r} parameter")
        return name

    def _converter(self, signature: inspect.Signature, result_param: str | None) -> Any:
        model = self._model(signature, result_param)
        if isinstance(model, _Unresolved):
            return DeferredConverter(model.annotation, getattr(self._func, "__globals__", {}))
        return converter_for(model)

    def _model(self, signature: inspect.Signature, result_param: str | None) -> Any:
        """model=, else the Result parameter's type (the return annotation then describes the
        hook's value), else the return annotation. Only JSON responses are converted."""
        if self._spec.model is not None:
            if self._spec.returns != "json" or self._spec.stream is not None:
                raise ValueError("model= needs a JSON response (returns='json', no stream)")
            return self._spec.model
        if self._spec.returns != "json" or self._spec.stream is not None:
            return None
        if result_param is not None:
            annotation = signature.parameters[result_param].annotation
        else:
            annotation = signature.return_annotation
        evaluated = self._evaluated(annotation)
        if evaluated is None and isinstance(annotation, str):
            return _Unresolved(annotation)
        return strip_annotated(evaluated)

    def _expected(self) -> frozenset[int] | None:
        expected = self._spec.expected
        if expected is None:
            return None
        if isinstance(expected, int):
            return frozenset({expected})
        return frozenset(expected)

    def _returns(self) -> str:
        if self._spec.returns not in RETURN_MODES:
            raise ValueError(f"returns must be one of {RETURN_MODES}")
        return self._spec.returns


class _Unresolved(NamedTuple):
    """A string annotation that names something not defined yet."""

    annotation: str


def _names(template: ValueTemplate | None) -> frozenset[str]:
    return frozenset() if template is None else frozenset(template.names)


def _is_result(annotation: Any) -> bool:
    return annotation is Result or isinstance(annotation, Result)


def _as_target(annotation: Any) -> ArgumentTarget | None:
    if isinstance(annotation, ArgumentTarget):
        return annotation
    if isinstance(annotation, type) and issubclass(annotation, ArgumentTarget):
        return annotation()
    return None
