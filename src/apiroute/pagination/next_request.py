from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from apiroute.request_options import RequestOptions


@dataclass(frozen=True)
class NextRequest:
    """How to ask for the next page: query and body values merged over the caller's arguments,
    or a URL (absolute, or relative to the page's) replacing the request's URL and query."""

    query: Mapping[str, Any] | None = None
    body: Any = None
    url: str | None = None

    def options(self) -> RequestOptions:
        return RequestOptions(query=self.query, body=self.body, url=self.url, returns="response")
