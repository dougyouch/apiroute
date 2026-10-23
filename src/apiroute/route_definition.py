import inspect
from dataclasses import dataclass
from typing import NamedTuple

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
