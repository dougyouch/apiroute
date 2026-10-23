from collections.abc import Mapping
from typing import Any

from apiroute.client_config import ClientConfig
from apiroute.request_options import RequestOptions
from apiroute.route_decorator import RouteDecorator
from apiroute.route_definition import RouteDefinition
from apiroute.route_executor import RouteExecutor
from apiroute.route_method import RouteMethod
from apiroute.router_view import RouterView
from apiroute.section_accessor import SectionAccessor


class Router:
    """What clients and sections share: class config, compiled routes, nested sections.

    Subclasses provide _root (the client that owns the connection) and _request_config().
    """

    _config = ClientConfig()

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls._config = ClientConfig.from_class(cls)
        lazy = cls._config.compile_routes == "lazy"
        for name, value in list(vars(cls).items()):
            if isinstance(value, RouteDecorator):
                value = value.generated_method(cls, name)
                setattr(cls, name, value)
            if isinstance(value, RouteMethod):
                if lazy:
                    value.defer(cls, name)
                else:
                    value.compile(cls, name)
        SectionAccessor.install(cls)

    @property
    def aio(self) -> RouterView:
        """The async side of this object: `await client.aio.get_user(...)`."""
        return RouterView(self, RequestOptions(), is_async=True)

    def with_options(self, **options: Any) -> RouterView:
        """A view of this object whose route calls also send these options:
        headers, query, body (merged over a dict body), timeout, retries (a Retries or a
        number of attempts) and returns."""
        return RouterView(self, RequestOptions(**options))

    def _call_route(
        self, definition: RouteDefinition, values: Mapping[str, Any], options: RequestOptions
    ) -> Any:
        return RouteExecutor(self, definition, options).execute(values)

    async def _call_route_async(
        self, definition: RouteDefinition, values: Mapping[str, Any], options: RequestOptions
    ) -> Any:
        return await RouteExecutor(self, definition, options).execute_async(values)
