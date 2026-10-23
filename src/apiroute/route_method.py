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
        self.__signature__ = self.definition.call_signature

    def __call__(self, router: Any, *args: Any, **kwargs: Any) -> Any:
        """Called through the class, like an unbound method: Api.get_user(client, ...)."""
        return self.bind(router, RequestOptions())(*args, **kwargs)

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return self
        return self.bind(instance, RequestOptions())

    def bind(self, router: Any, options: RequestOptions, is_async: bool = False) -> Callable:
        """The route as a method of router; a coroutine function when is_async."""
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
