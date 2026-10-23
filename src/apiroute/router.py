from collections.abc import Mapping
from typing import Any

from apiroute.client_config import ClientConfig
from apiroute.options_view import OptionsView
from apiroute.request_options import RequestOptions
from apiroute.route_decorator import RouteDecorator
from apiroute.route_definition import RouteDefinition
from apiroute.route_executor import RouteExecutor
from apiroute.route_method import RouteMethod
from apiroute.section_accessor import SectionAccessor


class Router:
    """What clients and sections share: class config, compiled routes, nested sections.

    Subclasses provide _root (the client that owns the connection) and _request_config().
    """

    _config = ClientConfig()

    def __init_subclass__(cls, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        cls._config = ClientConfig.from_class(cls)
        for name, value in list(vars(cls).items()):
            if isinstance(value, RouteDecorator):
                value = value.generated_method(cls, name)
                setattr(cls, name, value)
            if isinstance(value, RouteMethod):
                value.compile(cls, name)
        SectionAccessor.install(cls)

    def with_options(self, **options: Any) -> OptionsView:
        """A view of this object whose route calls also send these options:
        headers, query, body (merged over a dict body), timeout, retries (a Retries or a
        number of attempts) and returns."""
        return OptionsView(self, RequestOptions(**options))

    def _call_route(
        self, definition: RouteDefinition, values: Mapping[str, Any], options: RequestOptions
    ) -> Any:
        return RouteExecutor(self, definition, options).execute(values)
