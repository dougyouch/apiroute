import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Concatenate

from apiroute.graphql.graphql_paginator import GraphQLPaginator
from apiroute.graphql.graphql_persisted_call import GraphQLPersistedCall
from apiroute.graphql.graphql_route_builder import GraphQLRouteBuilder
from apiroute.request_options import RequestOptions
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.route_method import P, R, RouteMethod
from apiroute.route_spec import RouteSpec


class GraphQLRouteMethod(RouteMethod[P, R]):
    """A RouteMethod whose spec is built from its GraphQL operation when it is compiled, since
    the variables are matched against the method's parameters and its class's attributes.

    The document is validated against the graphql_schema of its class or, for a section that
    sets none, of the nearest class enclosing it. A section's routes compile before the
    enclosing classes exist, so those report themselves through nested_in."""

    def __init__(self, func: Callable[Concatenate[Any, P], R], builder: GraphQLRouteBuilder):
        super().__init__(func, None)
        self._builder = builder
        self._enclosing: list[type] = []
        self._schema_checked = False
        self._paginator: GraphQLPaginator | None = None
        self._variants: dict[str, RouteMethod] = {}
        self._unsupported: weakref.WeakSet = weakref.WeakSet()  # clients without APQ

    def _spec_for(self, owner: type, name: str) -> RouteSpec:
        with _labelled(owner, name):
            spec = self._builder.spec(owner, name, self._func)
            self._paginator = self._builder.paginator(name, self._func)
            self._variants = self._compiled_variants(owner, name, spec)
            self._check_schema(owner)
        return spec

    def bind(self, router: Any, options: RequestOptions, is_async: bool = False) -> Callable:
        """The route as a method of router; for a paginate= route, one returning an iterator
        (an async iterator when is_async) over the connection's items. Each call, or page,
        goes through persisted queries when the route has them."""
        call = self._bound(router, options, is_async)
        if self._paginator is None:
            return call

        def page_call(cursor: Any) -> Callable:
            if cursor is None:
                return call
            cursor_options = RequestOptions(body={self._builder.cursor: cursor})
            return self._bound(router, options.merged(cursor_options), is_async)

        return self._paginator.wrap(page_call, is_async)

    def _bound(self, router: Any, options: RequestOptions, is_async: bool) -> Callable:
        full = super().bind(router, options, is_async)  # compiles the route, and its variants
        if not self._variants:
            return full
        hashed = self._variants["hash"].bind(router, options, is_async)
        register = self._variants["register"].bind(router, options, is_async)
        persisted = GraphQLPersistedCall(hashed, register, full, self._unsupported, router._root)
        return persisted.bound(is_async)

    def _compiled_variants(self, owner: type, name: str, spec: RouteSpec) -> dict[str, RouteMethod]:
        """The same route sending a hash-only and a registering body, for persisted=True."""
        variants = {}
        for mode, variant_spec in self._builder.persisted_specs(spec).items():
            variant = RouteMethod(self._func, variant_spec)
            variant.compile(owner, name)
            variants[mode] = variant
        return variants

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
