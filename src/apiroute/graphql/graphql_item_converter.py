import inspect
from collections.abc import Callable
from typing import Any

from apiroute.graphql.graphql_paginator import item_type
from apiroute.response_converter import converter_for


class GraphQLItemConverter:
    """Converts a paginated route's items: to model= when given, else to X from the method's
    Iterator[X]-style return annotation. A string annotation naming something not defined yet
    (`-> "Iterator[Issue]"` above `class Issue`) is resolved on first use."""

    def __init__(self, model: Any, func: Callable):
        self._model = model
        self._func = func
        self._converter: Any = None
        self._resolved = False

    def convert(self, item: Any) -> Any:
        if not self._resolved:
            self._converter = converter_for(self._item_model())
            self._resolved = True
        return item if self._converter is None else self._converter.convert(item)

    def _item_model(self) -> Any:
        if self._model is not None:
            return self._model
        annotation = inspect.signature(self._func).return_annotation
        if isinstance(annotation, str):
            annotation = eval(annotation, getattr(self._func, "__globals__", {}))  # noqa: S307
        return item_type(annotation)
