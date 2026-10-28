from apiroute.pagination.dotted_path import DottedPath
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page
from apiroute.pagination.strategy import Strategy


class ItemCursor(Strategy):
    """Stripe's style: the next page starts after the last item, sending its field (its id) as
    param, while the body's has_more is true."""

    def __init__(
        self,
        param: str = "starting_after",
        field: str = "id",
        has_more: str = "has_more",
        items: str = "data",
    ):
        super().__init__(items)
        self._param = param
        self._field = field
        self._has_more = DottedPath(has_more)

    def next(self, page: Page) -> NextRequest | None:
        if not self._has_more.read(page.data):
            return None
        if not page.items:
            raise ValueError(f"{self._has_more.path} is true on an empty page; paging can't go on")
        last = page.items[-1]
        value = last.get(self._field) if isinstance(last, dict) else None
        if value is None:
            raise ValueError(f"the page's last item has no {self._field!r} to page from")
        return NextRequest(query={self._param: value})
