import inspect
from typing import Any

from apiroute.request_options import RequestOptions
from apiroute.route_method import RouteMethod
from apiroute.section_accessor import SectionAccessor


class OptionsView:
    """A client or section seen through with_options: its routes send these options too.

    Everything that isn't a route or section is read straight from the wrapped object.
    """

    def __init__(self, router: Any, options: RequestOptions):
        self._router = router
        self._options = options

    def with_options(self, **options: Any) -> "OptionsView":
        return OptionsView(self._router, self._options.merged(RequestOptions(**options)))

    def __getattr__(self, name: str) -> Any:
        attribute = inspect.getattr_static(type(self._router), name, None)
        if isinstance(attribute, RouteMethod):
            return attribute.bind(self._router, self._options)
        if isinstance(attribute, SectionAccessor):
            return OptionsView(getattr(self._router, name), self._options)
        return getattr(self._router, name)
