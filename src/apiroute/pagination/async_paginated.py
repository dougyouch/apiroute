from collections.abc import AsyncIterator, Callable
from typing import Any

from apiroute.pagination.page import Page


class AsyncPaginated(AsyncIterator[Any]):
    """Paginated through .aio: async for yields the items of every page, each page requested
    when iteration reaches it, and pages() is an async iterator over whole Page objects."""

    def __init__(self, pages: Callable[[], AsyncIterator[Page]], convert: Callable[[Any], Any]):
        self._pages = pages
        self._convert = convert
        self._items: AsyncIterator[Any] | None = None

    async def __anext__(self) -> Any:
        if self._items is None:
            self._items = self._converted_items()
        return await self._items.__anext__()

    def pages(self) -> AsyncIterator[Page]:
        return self._pages()

    async def _converted_items(self) -> AsyncIterator[Any]:
        async for page in self._pages():
            for item in page.items:
                yield self._convert(item)
