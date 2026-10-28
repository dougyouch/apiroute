from apiroute.pagination.dotted_path import DottedPath
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page
from apiroute.pagination.strategy import Strategy


class PageNumber(Strategy):
    """Numbered pages: param is the page number, start the first one's. Paging stops at an
    empty page; at the body's total_pages when it gives one; otherwise, when size names the
    page-size parameter and the request sent it, at a page with fewer items than that.

    The short-page rule is a guess: a server that caps the page size below what was asked
    makes a full page look short. Prefer total_pages when the API gives it."""

    def __init__(
        self,
        param: str = "page",
        start: int = 1,
        size: str | None = None,
        total_pages: str | None = None,
        items: str = "",
    ):
        super().__init__(items)
        self._param = param
        self._start = start
        self._size = size
        self._total_pages = None if total_pages is None else DottedPath(total_pages)

    def next(self, page: Page) -> NextRequest | None:
        number = self._number(page)
        if not page.items or self._is_last(page, number):
            return None
        return NextRequest(query={self._param: number + 1})

    def _number(self, page: Page) -> int:
        sent = page.sent(self._param)
        return self._start if sent is None else int(sent)

    def _is_last(self, page: Page, number: int) -> bool:
        total = None if self._total_pages is None else self._total_pages.read(page.data)
        if total is not None:
            return number - self._start + 1 >= int(total)
        size = None if self._size is None else page.sent(self._size)
        return size is not None and len(page.items) < int(size)
