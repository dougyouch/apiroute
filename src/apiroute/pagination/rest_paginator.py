import functools
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import replace
from typing import Any

import httpx

from apiroute.pagination.async_paginated import AsyncPaginated
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.page import Page
from apiroute.pagination.paginated import Paginated
from apiroute.unexpected_response import UnexpectedResponse


class RestPaginator:
    """Turns a bound REST route into a Paginated over its pages' items. Each page is an
    ordinary call, so it gets the client's headers, hooks, retries and status checks.

    page_call(request) gives the bound call for a page, returning its httpx.Response: the
    route as called for the first (request None), and with the strategy's NextRequest merged
    over the call after that. Paging raises ValueError rather than loop on a request that
    repeats the last one, or send the client's credentials to a next URL on another host."""

    def __init__(
        self,
        operation: str,
        strategy: Any,
        convert: Callable[[Any], Any],
        base_url: str | None,
        redact_url: Callable[[str], str] = str,
    ):
        self._operation = operation
        self._strategy = strategy
        self._convert = convert
        self._base_url = base_url
        self._redact_url = redact_url

    def wrap(self, page_call: Callable[[NextRequest | None], Callable], is_async: bool) -> Callable:
        first = page_call(None)
        signature = first.__signature__

        def paged(*args: Any, **kwargs: Any) -> Any:
            signature.bind(*args, **kwargs)  # wrong arguments fail on the call, not later
            if is_async:
                return AsyncPaginated(
                    lambda: self._async_pages(page_call, args, kwargs), self._convert
                )
            return Paginated(lambda: self._pages(page_call, args, kwargs), self._convert)

        functools.update_wrapper(paged, first)
        paged.__signature__ = signature
        return paged

    def _pages(self, page_call: Callable, args: tuple, kwargs: dict) -> Iterator[Page]:
        request: NextRequest | None = None
        index = 0
        while True:
            page = self._page(page_call(request)(*args, **kwargs), request, index)
            yield page
            request = self._next(page)
            if request is None:
                return
            index += 1

    async def _async_pages(
        self, page_call: Callable, args: tuple, kwargs: dict
    ) -> AsyncIterator[Page]:
        request: NextRequest | None = None
        index = 0
        while True:
            page = self._page(await page_call(request)(*args, **kwargs), request, index)
            yield page
            request = self._next(page)
            if request is None:
                return
            index += 1

    def _page(self, response: httpx.Response, request: NextRequest | None, index: int) -> Page:
        page = Page(self._decoded(response), response, request, index)
        return replace(page, items=self._checked(self._strategy.items, page))

    def _decoded(self, response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            shown_url = self._redact_url(str(response.request.url))
            raise UnexpectedResponse(
                self._operation, response, "invalid JSON body", shown_url=shown_url
            ) from error

    def _next(self, page: Page) -> NextRequest | None:
        following = self._checked(self._strategy.next, page)
        if following is None:
            return None
        if following.url is not None:
            following = replace(following, url=self._same_origin(following.url, page))
        if following == page.request:
            raise ValueError(
                f"{self._operation}: the next page's request is the same as this page's "
                f"({self._shown(following)}); paging would never end"
            )
        return following

    def _checked(self, step: Callable[[Page], Any], page: Page) -> Any:
        try:
            return step(page)
        except ValueError as error:
            raise ValueError(f"{self._operation}: page {page.index + 1}: {error}") from error

    def _same_origin(self, url: str, page: Page) -> str:
        """url resolved against the page's own URL; a ValueError when it's on another scheme,
        host or port than base_url, which would send it the client's credentials."""
        absolute = page.response.request.url.join(url)
        base = httpx.URL(self._base_url or "")
        if _origin(absolute) != _origin(base):
            raise ValueError(
                f"{self._operation}: the next page's URL is on {absolute.scheme}://"
                f"{absolute.netloc.decode()}, not the client's {base.scheme}://"
                f"{base.netloc.decode()}; it wasn't followed"
            )
        return str(absolute)

    def _shown(self, request: NextRequest) -> str:
        if request.url is not None:
            return self._redact_url(request.url)
        return repr(request.body if request.query is None else request.query)


def _origin(url: httpx.URL) -> tuple[str, str, int | None]:
    return url.scheme, url.host, url.port
