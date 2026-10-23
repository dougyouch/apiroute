import inspect
from dataclasses import dataclass
from typing import Any, NamedTuple

from apiroute.path_template import PathTemplate
from apiroute.value_template import ValueTemplate


class ArgumentBinding(NamedTuple):
    """A parameter annotated with Query or Header, and the name it is sent under."""

    param: str
    location: str
    key: str


@dataclass(frozen=True)
class RouteDefinition:
    """A compiled route: everything the request builder needs, checked once at class creation."""

    name: str
    http_method: str
    path: PathTemplate
    query: ValueTemplate | None
    body: ValueTemplate | None
    literal_body: str | bytes | None
    body_param: str | None
    bindings: tuple[ArgumentBinding, ...]
    expected: frozenset[int] | None
    returns: str
    timeout: float | None
    signature: inspect.Signature
    # The keyword-only parameter annotated Result, if any; when set, the method body runs
    # after the request as a response hook
    result_param: str | None = None
    # "file", "io" or "iter" for streaming routes, and the parameter holding the destination
    stream: str | None = None
    stream_param: str | None = None
    # Turns parsed JSON into the route's model type; None returns the JSON as parsed
    converter: Any = None
    headers: ValueTemplate | None = None
    body_format: Any = None
    decoder: Any = None
    operation: str | None = None

    @property
    def call_signature(self) -> inspect.Signature:
        """The signature callers see: the method's, without the Result parameter."""
        if self.result_param is None:
            return self.signature
        parameters = [p for p in self.signature.parameters.values() if p.name != self.result_param]
        return self.signature.replace(parameters=parameters)
