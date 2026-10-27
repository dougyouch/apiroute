from collections.abc import Callable
from typing import Any, Concatenate

from apiroute.graphql.graphql_route_builder import GraphQLRouteBuilder
from apiroute.graphql.graphql_route_method import GraphQLRouteMethod
from apiroute.route_decorator import RouteDecorator
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.route_method import P, R


class GraphQLRouteDecorator(RouteDecorator):
    """What graphql_route(...) returns: applied to a def, or left on the class as is, in which
    case the router generates the method's signature from the operation's variables."""

    def __init__(self, builder: GraphQLRouteBuilder):
        self._builder = builder

    def __call__(self, func: Callable[Concatenate[Any, P], R]) -> GraphQLRouteMethod[P, R]:
        return GraphQLRouteMethod(func, self._builder)

    def generated_method(self, owner: type, name: str) -> GraphQLRouteMethod[..., Any]:
        try:
            stub = self._builder.stub(owner, name)
        except (TypeError, ValueError) as error:
            raise RouteDefinitionError(f"{owner.__qualname__}.{name}: {error}") from error
        return GraphQLRouteMethod(stub, self._builder)
