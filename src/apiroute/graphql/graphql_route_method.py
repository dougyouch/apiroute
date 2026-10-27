from collections.abc import Callable

from apiroute.graphql.graphql_route_builder import GraphQLRouteBuilder
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.route_method import RouteMethod
from apiroute.route_spec import RouteSpec


class GraphQLRouteMethod(RouteMethod):
    """A RouteMethod whose spec is built from its GraphQL operation when it is compiled, since
    the variables are matched against the method's parameters and its class's attributes."""

    def __init__(self, func: Callable, builder: GraphQLRouteBuilder):
        super().__init__(func, None)
        self._builder = builder

    def _spec_for(self, owner: type, name: str) -> RouteSpec:
        try:
            return self._builder.spec(owner, name, self._func)
        except (TypeError, ValueError) as error:
            raise RouteDefinitionError(f"{owner.__qualname__}.{name}: {error}") from error
