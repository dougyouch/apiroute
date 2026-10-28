from collections.abc import Callable, Iterator
from typing import Any

from apiroute.pagination.page import Page


class Paginated(Iterator[Any]):
    """What a paginated route returns: an iterator over the items of every page, converted to
    the route's item type. Nothing is requested before iteration starts, and each page only
    when iteration reaches it; itertools.islice or break stop it early.

    pages() is a separate iteration over whole Page objects, from the first page again."""

    def __init__(self, pages: Callable[[], Iterator[Page]], convert: Callable[[Any], Any]):
        self._pages = pages
        self._convert = convert
        self._items: Iterator[Any] | None = None

    def __next__(self) -> Any:
        if self._items is None:
            self._items = self._converted_items()
        return next(self._items)

    def pages(self) -> Iterator[Page]:
        return self._pages()

    def _converted_items(self) -> Iterator[Any]:
        for page in self._pages():
            for item in page.items:
                yield self._convert(item)
