import functools
from collections.abc import Callable
from typing import Any

from apiroute.from_client import FROM_CLIENT
from apiroute.request_options import RequestOptions
from apiroute.route_compiler import RouteCompiler
from apiroute.route_definition import RouteDefinition
from apiroute.route_spec import RouteSpec


class RouteMethod:
    """What @route leaves on the class: binds to a client or section as a request method.

    The router compiles it in __init_subclass__, so a bad route fails when its class is created.
    """

    def __init__(self, func: Callable, spec: RouteSpec):
        self._func = func
        self._spec = spec
        self.definition: RouteDefinition | None = None
        functools.update_wrapper(self, func)

    def compile(self, owner: type, name: str) -> None:
        self.definition = RouteCompiler(owner.__qualname__, name, self._func, self._spec).compile()
        self.__signature__ = self.definition.signature

    def __call__(self, router: Any, *args: Any, **kwargs: Any) -> Any:
        """Called through the class, like an unbound method: Api.get_user(client, ...)."""
        return self.bind(router, RequestOptions())(*args, **kwargs)

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self
        return self.bind(instance, RequestOptions())

    def bind(self, router: Any, options: RequestOptions) -> Callable:
        definition = self.definition

        @functools.wraps(self._func)
        def call(*args: Any, **kwargs: Any) -> Any:
            bound = definition.signature.bind(router, *args, **kwargs)
            bound.apply_defaults()
            values = {
                name: value for name, value in bound.arguments.items() if value is not FROM_CLIENT
            }
            values.pop(next(iter(values)))  # self
            return router._call_route(definition, values, options)

        call.__signature__ = definition.signature.replace(
            parameters=list(definition.signature.parameters.values())[1:]
        )
        return call
