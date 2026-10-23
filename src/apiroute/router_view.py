import inspect
from typing import Any

from apiroute.lazy_attribute import LazyAttribute
from apiroute.request_options import RequestOptions
from apiroute.route_method import RouteMethod
from apiroute.section_accessor import SectionAccessor


class RouterView:
    """A client or section seen through with_options and/or .aio.

    Its routes send the view's options, and in an async view they return coroutines.
    Everything that isn't a route or section is read straight from the wrapped object.
    """

    def __init__(self, router: Any, options: RequestOptions, is_async: bool = False):
        self._router = router
        self._options = options
        self._is_async = is_async

    @property
    def is_async(self) -> bool:
        return self._is_async

    @property
    def aio(self) -> "RouterView":
        return RouterView(self._router, self._options, is_async=True)

    def with_options(self, **options: Any) -> "RouterView":
        merged = self._options.merged(RequestOptions(**options))
        return RouterView(self._router, merged, self._is_async)

    def __getattr__(self, name: str) -> Any:
        attribute = inspect.getattr_static(type(self._router), name, None)
        if isinstance(attribute, RouteMethod):
            return attribute.bind(self._router, self._options, self._is_async)
        if isinstance(attribute, SectionAccessor):
            return RouterView(getattr(self._router, name), self._options, self._is_async)
        if isinstance(attribute, LazyAttribute):
            return self._lazy(attribute, name)
        return getattr(self._router, name)

    def _lazy(self, attribute: LazyAttribute, name: str) -> Any:
        """A lazy section keeps this view's options; a lazy .models view wraps this view."""
        loaded = attribute.load()
        if getattr(loaded, "_is_section", False):
            return RouterView(getattr(self._router, name), self._options, self._is_async)
        return loaded(self)
