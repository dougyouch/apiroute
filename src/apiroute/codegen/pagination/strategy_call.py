import inspect
from typing import Any

from apiroute.pagination import Cursor, ItemCursor, NextUrl, Offset, PageNumber

STRATEGIES = {
    "cursor": Cursor,
    "item_cursor": ItemCursor,
    "next_url": NextUrl,
    "page": PageNumber,
    "offset": Offset,
}


class StrategyCall:
    """A strategy as a rule names it, {"type": "item_cursor", "items": "data"}: checked against
    the strategy's own arguments, so a typo fails generation rather than the generated code."""

    def __init__(self, kind: str, arguments: dict[str, Any]):
        if kind not in STRATEGIES:
            raise ValueError(f"unknown type {kind!r}; one of {', '.join(STRATEGIES)}")
        self._class = STRATEGIES[kind]
        try:
            inspect.signature(self._class).bind(**arguments)
            self._class(**arguments)
        except TypeError as error:
            raise ValueError(f"{kind}: {error}") from error
        self.arguments = arguments

    @property
    def class_name(self) -> str:
        return self._class.__name__

    @property
    def items(self) -> str:
        """The dotted path to the items, as given or by the strategy's default."""
        default = inspect.signature(self._class).parameters["items"].default
        return self.arguments.get("items", default)
