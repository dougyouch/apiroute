from apiroute.pagination.dotted_path import DottedPath
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page
from apiroute.pagination.strategy import Strategy


class Offset(Strategy):
    """Offset and limit: the next page's param is this page's offset (0 when not sent) plus
    its number of items. Paging stops at an empty page; when the body's total is reached, if
    it gives one; otherwise at a page with fewer items than the limit the request sent.

    The short-page rule is a guess: a server that caps the limit below what was asked makes a
    full page look short. Prefer total when the API gives it."""

    def __init__(
        self,
        param: str = "offset",
        limit: str = "limit",
        total: str | None = None,
        items: str = "",
    ):
        super().__init__(items)
        self._param = param
        self._limit = limit
        self._total = None if total is None else DottedPath(total)

    def next(self, page: Page) -> NextRequest | None:
        offset = int(page.sent(self._param) or 0) + len(page.items)
        if not page.items or self._is_last(page, offset):
            return None
        return NextRequest(query={self._param: offset})

    def _is_last(self, page: Page, offset: int) -> bool:
        total = None if self._total is None else self._total.read(page.data)
        if total is not None:
            return offset >= int(total)
        limit = page.sent(self._limit)
        return limit is not None and len(page.items) < int(limit)
