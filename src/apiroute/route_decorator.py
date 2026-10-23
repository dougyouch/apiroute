from collections.abc import Callable

from apiroute.generated_signature import GeneratedSignature
from apiroute.route_method import RouteMethod
from apiroute.route_spec import RouteSpec


class RouteDecorator:
    """What route(...) returns.

    Applied to a def, it makes a RouteMethod from that function. Left on the class as is
    (get_user = route("/users/:username")), the router turns it into a RouteMethod whose
    signature is generated from the route's placeholders, as the Ruby gem does.
    """

    def __init__(self, spec: RouteSpec):
        self._spec = spec

    def __call__(self, func: Callable) -> RouteMethod:
        return RouteMethod(func, self._spec)

    def generated_method(self, owner: type, name: str) -> RouteMethod:
        return RouteMethod(GeneratedSignature(owner, name, self._spec).function(), self._spec)
