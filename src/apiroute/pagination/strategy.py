from typing import Any

from apiroute.pagination.dotted_path import DottedPath
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page


class Strategy:
    """The base of the built-in strategies: a page's items are the list at the dotted path
    items, or the body itself when it's "". A custom strategy needn't extend it; any object
    with items(page) and next(page) will do."""

    def __init__(self, items: str = ""):
        self._items = DottedPath(items)

    def items(self, page: Page) -> list[Any]:
        return self._items.list_in(page.data)

    def next(self, page: Page) -> NextRequest | None:
        raise NotImplementedError
