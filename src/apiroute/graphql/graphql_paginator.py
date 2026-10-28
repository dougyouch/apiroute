import functools
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any


class GraphQLPaginator:
    """Turns a bound GraphQL route into an iterator over a Relay connection's items, across
    pages: each page is an ordinary call, made when iteration reaches it, with the previous
    page's pageInfo.endCursor set as the cursor variable. Items are the connection's nodes, or
    each edge's node, converted when the route has an item converter.

    page_call(cursor) gives the bound call for a page: the route as called for the first
    (cursor None), and with the cursor variable set over its variables after that, so the
    method needn't have a parameter for it."""

    def __init__(self, operation: str, path: str, converter: Any = None):
        self._operation = operation
        self._path = path
        self._keys = path.split(".")
        self._converter = converter

    def wrap(self, page_call: Callable[[Any], Callable], is_async: bool) -> Callable:
        first = page_call(None)
        signature = first.__signature__

        def paged(*args: Any, **kwargs: Any) -> Any:
            signature.bind(*args, **kwargs)  # wrong arguments fail on the call, not later
            if is_async:
                return self._async_items(page_call, args, kwargs)
            return self._items(page_call, args, kwargs)

        functools.update_wrapper(paged, first)
        paged.__signature__ = signature
        return paged

    def _items(self, page_call: Callable, args: tuple, kwargs: dict) -> Iterator[Any]:
        cursor = None
        while True:
            connection = self._connection(page_call(cursor)(*args, **kwargs))
            if connection is None:
                return
            yield from self._page(connection)
            cursor = self._next_cursor(connection, cursor)
            if cursor is None:
                return

    async def _async_items(
        self, page_call: Callable, args: tuple, kwargs: dict
    ) -> AsyncIterator[Any]:
        cursor = None
        while True:
            connection = self._connection(await page_call(cursor)(*args, **kwargs))
            if connection is None:
                return
            for item in self._page(connection):
                yield item
            cursor = self._next_cursor(connection, cursor)
            if cursor is None:
                return

    def _connection(self, data: Any) -> dict[str, Any] | None:
        """The connection along the path; None when something on the way is null."""
        for key in self._keys:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
        return data if isinstance(data, dict) else None

    def _page(self, connection: dict[str, Any]) -> list[Any]:
        if "nodes" in connection:
            items = connection["nodes"] or []
        elif "edges" in connection:
            items = [
                edge.get("node") if edge is not None else None for edge in connection["edges"] or []
            ]
        else:
            raise ValueError(
                f"{self._operation}: {self._path} selects neither nodes nor edges {{ node }}"
            )
        return [self._converted(item) for item in items]

    def _converted(self, item: Any) -> Any:
        if item is None or self._converter is None:
            return item
        return self._converter.convert(item)

    def _next_cursor(self, connection: dict[str, Any], previous: Any) -> Any:
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict) or not {"hasNextPage", "endCursor"} <= page_info.keys():
            raise ValueError(
                f"{self._operation}: paginate= needs the operation to select "
                f"pageInfo {{ hasNextPage endCursor }} on {self._path}"
            )
        if not page_info["hasNextPage"]:
            return None
        cursor = page_info["endCursor"]
        if cursor is None or cursor == previous:
            problem = "no endCursor" if cursor is None else f"the same endCursor ({cursor!r}) again"
            raise ValueError(
                f"{self._operation}: the server answered hasNextPage with {problem}; "
                "paging would never end"
            )
        return cursor
