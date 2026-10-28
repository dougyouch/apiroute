from dataclasses import dataclass, field
from typing import Any

import httpx

from apiroute.pagination.next_request import NextRequest


@dataclass(frozen=True)
class Page:
    """One page of a paginated route, as strategies and .pages() see it.

    data is the decoded JSON body, response the httpx.Response, request the NextRequest that
    asked for it (None for the first page, made with the caller's arguments), index its
    zero-based position, and items its list of items as decoded (not converted).
    """

    data: Any
    response: httpx.Response
    request: NextRequest | None
    index: int
    items: list[Any] = field(default_factory=list)

    def sent(self, name: str) -> str | None:
        """The query parameter name as this page's request sent it, or None when it didn't."""
        return self.response.request.url.params.get(name)
