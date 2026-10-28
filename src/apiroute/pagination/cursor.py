from apiroute.pagination.dotted_path import DottedPath
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page
from apiroute.pagination.strategy import Strategy

LOCATIONS = ("query", "body")


class Cursor(Strategy):
    """An opaque token for the next page, read from the body's dotted path token (Slack's
    "response_metadata.next_cursor", Google's "nextPageToken") or from the response header
    header, sent as param in the query or, with location="body", the body. Paging stops when
    the token is missing, null or ""."""

    def __init__(
        self,
        param: str,
        token: str = "next_cursor",
        header: str | None = None,
        location: str = "query",
        items: str = "",
    ):
        super().__init__(items)
        if location not in LOCATIONS:
            raise ValueError(f"location must be one of {LOCATIONS}")
        self._param = param
        self._token = DottedPath(token)
        self._header = header
        self._location = location

    def next(self, page: Page) -> NextRequest | None:
        token = self._read_token(page)
        if token is None or token == "":
            return None
        return NextRequest(**{self._location: {self._param: token}})

    def _read_token(self, page: Page) -> object:
        if self._header is not None:
            return page.response.headers.get(self._header)
        return self._token.read(page.data)
