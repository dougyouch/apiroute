import functools
import inspect
from collections.abc import Callable
from typing import Any

from apiroute.class_declaration import declares
from apiroute.from_client import FROM_CLIENT
from apiroute.graphql.graphql_body import GraphQLBody
from apiroute.graphql.graphql_decoder import GraphQLDecoder
from apiroute.graphql.graphql_document import GraphQLDocument
from apiroute.graphql.graphql_item_converter import GraphQLItemConverter
from apiroute.graphql.graphql_operation import GraphQLOperation
from apiroute.graphql.graphql_paginator import GraphQLPaginator
from apiroute.graphql.graphql_route_options import GraphQLRouteOptions
from apiroute.graphql.graphql_schema_check import check_against_schema
from apiroute.graphql.graphql_schema_loader import load_schema
from apiroute.graphql.graphql_syntax_check import check_syntax
from apiroute.graphql.graphql_variable_binder import GraphQLVariableBinder
from apiroute.route_spec import RouteSpec

ACCEPT = "application/graphql-response+json, application/json"
# GraphQL-over-HTTP servers answer a request they can't run with 400 and an errors body
EXPECTED = (200, 400)
_KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY


class GraphQLRouteBuilder:
    """Turns graphql_route's options into a RouteSpec once the route's class and name are
    known: its variables become the body template, filled from the method's arguments."""

    def __init__(self, options: GraphQLRouteOptions):
        self._options = options

    def spec(self, owner: type, name: str, func: Callable) -> RouteSpec:
        options = self._options
        operation = self._operation
        label = self._label(name)
        params = list(inspect.signature(func).parameters)[1:]
        if options.paginate:
            self._check_pagination(operation)
        return RouteSpec(
            method="POST",
            path=options.path,
            query=None,
            body=self._binder(owner).template(params),
            expected=EXPECTED,
            returns="json",
            timeout=options.timeout,
            # a paginated route converts items, not the page's data
            model=Any if options.paginate else options.model,
            headers={"Accept": ACCEPT, **(options.headers or {})},
            body_format=GraphQLBody(options.document, operation.name),
            decoder=GraphQLDecoder(label, options.data, options.errors),
            operation=label,
            idempotent=self._idempotent(operation),
        )

    def paginator(self, name: str, func: Callable) -> GraphQLPaginator | None:
        """What turns the bound method into an iterator over pages, for paginate= routes."""
        options = self._options
        if not options.paginate:
            return None
        converter = GraphQLItemConverter(options.model, func)
        return GraphQLPaginator(self._label(name), options.paginate, converter)

    def persisted_specs(self, spec: RouteSpec) -> dict[str, RouteSpec]:
        """For persisted=True: the route's spec as hash-only and as registering requests."""
        if not self._options.persisted:
            return {}
        name = self._operation.name
        document = self._options.document
        return {
            mode: spec._replace(body_format=GraphQLBody(document, name, persisted=mode))
            for mode in ("hash", "register")
        }

    @property
    def cursor(self) -> str:
        """The variable a paginated route's later pages set to the previous endCursor."""
        return self._options.cursor

    def check_schema(self, holder: type) -> None:
        """Validates the document against the graphql_schema holder declares, unless the route
        opted out with validate=False."""
        if self._options.validate:
            check_against_schema(self._options.document, load_schema(holder))

    def stub(self, owner: type, name: str) -> Callable:
        """The function behind a route written without a def: one keyword-only parameter per
        variable, required when the variable is, else defaulting to None (or the client's)."""
        binder = self._binder(owner)
        parameters = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        parameters += [
            self._parameter(owner, binder.param_name(variable.name), variable.required)
            for variable in self._operation.variables
        ]

        def stub(*args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError("generated routes are called through the client")

        stub.__name__ = name
        stub.__qualname__ = f"{owner.__qualname__}.{name}"
        stub.__module__ = owner.__module__
        stub.__doc__ = self._options.document
        stub.__signature__ = inspect.Signature(parameters)
        return stub

    def _label(self, name: str) -> str:
        return self._operation.name or self._options.operation_name or name

    def _check_pagination(self, operation: GraphQLOperation) -> None:
        cursor = self._options.cursor
        if self._options.data is not None:
            raise ValueError("paginate= returns the connection's items; it can't take data=")
        if cursor not in {variable.name for variable in operation.variables}:
            raise ValueError(f"paginate= needs the operation to declare ${cursor}: String")

    @functools.cached_property
    def _operation(self) -> GraphQLOperation:
        check_syntax(self._options.document)
        return GraphQLDocument(self._options.document).operation(self._options.operation_name)

    def _binder(self, owner: type) -> GraphQLVariableBinder:
        return GraphQLVariableBinder(self._operation.variables, self._options.variables, owner)

    def _idempotent(self, operation: GraphQLOperation) -> bool:
        if self._options.idempotent is not None:
            return self._options.idempotent
        return operation.type != "mutation"

    @staticmethod
    def _parameter(owner: type, name: str, required: bool) -> inspect.Parameter:
        if declares(owner, name):
            return inspect.Parameter(name, _KEYWORD_ONLY, default=FROM_CLIENT)
        if required:
            return inspect.Parameter(name, _KEYWORD_ONLY)
        return inspect.Parameter(name, _KEYWORD_ONLY, default=None)
