from collections.abc import Callable
from typing import Any, Concatenate

from apiroute.generated_signature import GeneratedSignature
from apiroute.route_method import P, R, RouteMethod
from apiroute.route_spec import RouteSpec


class RouteDecorator:
    """What route(...) returns.

    Applied to a def, it makes a RouteMethod from that function. Left on the class as is
    (get_user = route("/users/:username")), the router turns it into a RouteMethod whose
    signature is generated from the route's placeholders, as the Ruby gem does.
    """

    def __init__(self, spec: RouteSpec):
        self._spec = spec

    def __call__(self, func: Callable[Concatenate[Any, P], R]) -> RouteMethod[P, R]:
        return RouteMethod(func, self._spec)

    def __get__(self, instance: Any, owner: type) -> Callable[..., Any]:
        """For type checkers: a route written without a def has a signature generated when its
        class is created, so it's a callable taking anything. The router replaces this object
        with that route then, so on a client or section this never runs."""
        return self

    def generated_method(self, owner: type, name: str) -> RouteMethod:
        return RouteMethod(GeneratedSignature(owner, name, self._spec).function(), self._spec)
