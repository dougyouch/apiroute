import inspect
from collections.abc import Mapping
from typing import Any


class PlaceholderResolver:
    """Finds the value for a {name}: the call's argument, else the root client's attribute.

    A method on the client is called, like the gem's {name} calling the client's method.
    """

    def __init__(self, values: Mapping[str, Any], root: Any):
        self._values = values
        self._root = root

    def __call__(self, name: str) -> Any:
        if name in self._values:
            return self._values[name]
        value = getattr(self._root, name)
        return value() if inspect.ismethod(value) else value
