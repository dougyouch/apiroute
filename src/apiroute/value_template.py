from collections.abc import Callable
from typing import Any

from apiroute.path_template import PLACEHOLDER

Resolve = Callable[[str], Any]
Renderer = Callable[[Resolve], Any]

_SCALARS = (str, int, float, bool, type(None))


class ValueTemplate:
    """A query or body template: dicts and lists whose strings may hold {name} placeholders.

    A string that is exactly '{name}' passes the value through with its type; placeholders
    inside text are formatted as strings. The template is compiled once, into closures.
    """

    def __init__(self, value: Any):
        self._names: dict[str, None] = {}
        self._render = self._compile(value)
        self.names = tuple(self._names)

    def render(self, resolve: Resolve) -> Any:
        return self._render(resolve)

    def _compile(self, value: Any) -> Renderer:
        if isinstance(value, dict):
            return self._compile_dict(value)
        if isinstance(value, (list, tuple)):
            return self._compile_list(value)
        if isinstance(value, str):
            return self._compile_string(value)
        if isinstance(value, _SCALARS):
            return lambda resolve: value
        raise TypeError(
            f"{type(value).__name__} values can't be used in a route template; "
            "pass them as an argument or a '{name}' placeholder"
        )

    def _compile_dict(self, value: dict) -> Renderer:
        items = [(key, self._compile(item)) for key, item in value.items()]
        return lambda resolve: {key: render(resolve) for key, render in items}

    def _compile_list(self, value: list | tuple) -> Renderer:
        items = [self._compile(item) for item in value]
        return lambda resolve: [render(resolve) for render in items]

    def _compile_string(self, text: str) -> Renderer:
        whole = PLACEHOLDER.fullmatch(text)
        if whole:
            name = whole.group(1)
            self._names[name] = None
            return lambda resolve: resolve(name)
        names = PLACEHOLDER.findall(text)
        if not names:
            return lambda resolve: text
        self._names.update(dict.fromkeys(names))
        return lambda resolve: PLACEHOLDER.sub(lambda match: str(resolve(match.group(1))), text)
