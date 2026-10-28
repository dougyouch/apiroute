from apiroute.pagination.dotted_path import DottedPath
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page
from apiroute.pagination.strategy import Strategy


class NextUrl(Strategy):
    """The next page is at a URL: the Link header's entry whose rel is link (GitHub's
    rel="next"), or, when path is given, the URL at that dotted path in the body (Django REST
    framework's "next"). Paging stops when there's none."""

    def __init__(self, link: str = "next", path: str | None = None, items: str = ""):
        super().__init__(items)
        self._link = link
        self._path = None if path is None else DottedPath(path)

    def next(self, page: Page) -> NextRequest | None:
        if self._path is not None:
            url = self._path.read(page.data)
        else:
            url = page.response.links.get(self._link, {}).get("url")
        return NextRequest(url=url) if url else None
