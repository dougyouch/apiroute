from collections.abc import Callable, Iterator
from contextlib import contextmanager

from apiroute.graphql.graphql_route_builder import GraphQLRouteBuilder
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.route_method import RouteMethod
from apiroute.route_spec import RouteSpec


class GraphQLRouteMethod(RouteMethod):
    """A RouteMethod whose spec is built from its GraphQL operation when it is compiled, since
    the variables are matched against the method's parameters and its class's attributes.

    The document is validated against the graphql_schema of its class or, for a section that
    sets none, of the nearest class enclosing it. A section's routes compile before the
    enclosing classes exist, so those report themselves through nested_in."""

    def __init__(self, func: Callable, builder: GraphQLRouteBuilder):
        super().__init__(func, None)
        self._builder = builder
        self._enclosing: list[type] = []
        self._schema_checked = False

    def _spec_for(self, owner: type, name: str) -> RouteSpec:
        with _labelled(owner, name):
            spec = self._builder.spec(owner, name, self._func)
            self._check_schema(owner)
        return spec

    def nested_in(self, root: type) -> None:
        self._enclosing.append(root)
        if self._definition is not None:  # compiled already; a lazy route checks on first use
            with _labelled(self._owner, self._name):
                self._check_schema(self._owner)

    def _check_schema(self, owner: type) -> None:
        if self._schema_checked:
            return
        holder = self._schema_holder(owner)
        if holder is not None:
            self._builder.check_schema(holder)
            self._schema_checked = True

    def _schema_holder(self, owner: type) -> type | None:
        """The first of the route's class and its enclosing classes to set graphql_schema;
        None when that class set it to None, or none sets it."""
        for cls in (owner, *self._enclosing):
            if hasattr(cls, "graphql_schema"):
                return None if cls.graphql_schema is None else cls
        return None


@contextmanager
def _labelled(owner: type, name: str) -> Iterator[None]:
    """Turns a TypeError or ValueError into a RouteDefinitionError naming the route."""
    try:
        yield
    except (TypeError, ValueError) as error:
        raise RouteDefinitionError(f"{owner.__qualname__}.{name}: {error}") from error
