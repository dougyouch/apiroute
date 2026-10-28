import functools
import inspect
from collections.abc import Callable
from typing import Any, Concatenate, Generic, ParamSpec, TypeVar, overload

from apiroute.from_client import FROM_CLIENT
from apiroute.pagination.rest_paginator import RestPaginator
from apiroute.request_options import RequestOptions
from apiroute.route_compiler import RouteCompiler
from apiroute.route_definition import RouteDefinition
from apiroute.route_spec import RouteSpec

# The decorated method's parameters (after self) and return type, so type checkers see
# client.get_user as the method's own signature
P = ParamSpec("P")
R = TypeVar("R")


class RouteMethod(Generic[P, R]):
    """What @route leaves on the class: binds to a client or section as a request method.

    The router compiles it in __init_subclass__, so a bad route fails when its class is
    created; with compile_routes = "lazy" it is compiled on first use instead.

    Type checkers see it, through an instance, as the decorated method without self.
    """

    def __init__(self, func: Callable[Concatenate[Any, P], R], spec: RouteSpec | None):
        self._func = func
        self._spec = spec
        self._definition: RouteDefinition | None = None
        self._owner: type | None = None
        self._name: str | None = None
        functools.update_wrapper(self, func)

    def compile(self, owner: type, name: str) -> None:
        self.defer(owner, name)
        spec = self._spec_for(owner, name)
        self._definition = RouteCompiler(owner.__qualname__, name, self._func, spec).compile()

    def _spec_for(self, owner: type, name: str) -> RouteSpec:
        """The spec to compile; a subclass may build it once the class and name are known."""
        return self._spec

    def nested_in(self, root: type) -> None:
        """Called when a class encloses this route's section (innermost first), once that
        class is created: a section's body runs before its enclosing class exists."""

    def defer(self, owner: type, name: str) -> None:
        """Remembers where the route lives, to compile it on first use."""
        self._owner = owner
        self._name = name

    @property
    def definition(self) -> RouteDefinition:
        if self._definition is None:
            if self._owner is None:
                raise RuntimeError(f"route {self._func.__name__} is not on a Client or Section")
            self.compile(self._owner, self._name)
        return self._definition

    @property
    def __signature__(self) -> inspect.Signature:
        return self.definition.call_signature

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Called through the class, like an unbound method: Api.get_user(client, ...).
        Typed loosely, so code a type checker reads as reaching a route through a class
        (mypy, for a nested Section) checks as Any rather than failing."""
        router, *rest = args
        return self.bind(router, RequestOptions())(*rest, **kwargs)

    @overload
    def __get__(self, instance: None, owner: type) -> "RouteMethod[P, R]": ...

    @overload
    def __get__(self, instance: object, owner: type) -> Callable[P, R]: ...

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self
        return self.bind(instance, RequestOptions())

    def bind(self, router: Any, options: RequestOptions, is_async: bool = False) -> Callable:
        """The route as a method of router; a coroutine function when is_async. A paginate=
        route returns a Paginated (an AsyncPaginated when is_async) over every page's items."""
        definition = self.definition
        if definition.paginate is None:
            return self._call(router, options, is_async)

        def page_call(request: Any) -> Callable:
            extra = RequestOptions(returns="response") if request is None else request.options()
            return self._call(router, options.merged(extra), is_async)

        paginator = RestPaginator(
            definition.operation or definition.name,
            definition.paginate,
            definition.converter.convert,
            router._request_config().base_url,
            router._root.redact_url,
        )
        return paginator.wrap(page_call, is_async)

    def _call(self, router: Any, options: RequestOptions, is_async: bool) -> Callable:
        """The route as a method making one request."""
        definition = self.definition
        func = self._func

        def values_of(args: tuple, kwargs: dict) -> dict[str, Any]:
            bound = definition.call_signature.bind(router, *args, **kwargs)
            bound.apply_defaults()
            values = {
                name: value for name, value in bound.arguments.items() if value is not FROM_CLIENT
            }
            values.pop(next(iter(values)))  # self
            return values

        def finish(values: dict[str, Any], result: Any) -> Any:
            """Runs the method body as the response hook when it takes a Result."""
            if definition.result_param is None:
                return result
            replaced = func(router, **values, **{definition.result_param: result})
            return result if replaced is None else replaced

        if is_async:

            @functools.wraps(func)
            async def call(*args: Any, **kwargs: Any) -> Any:
                values = values_of(args, kwargs)
                return finish(values, await router._call_route_async(definition, values, options))

        else:

            @functools.wraps(func)
            def call(*args: Any, **kwargs: Any) -> Any:
                values = values_of(args, kwargs)
                return finish(values, router._call_route(definition, values, options))

        call.__signature__ = definition.call_signature.replace(
            parameters=list(definition.call_signature.parameters.values())[1:]
        )
        return call
