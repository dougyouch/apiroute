"""Paging REST routes: route(..., paginate=<strategy>) makes a method return an iterator over
the items of every page, each page an ordinary request made when iteration reaches it.

    @route("GET", "/v1/customers", paginate=ItemCursor())
    def list_customers(self, limit: int = 100) -> Iterator[Customer]: ...

A strategy is any object with items(page) (the page's list of items) and next(page) (a
NextRequest for the following page, or None at the last). The built-in ones cover cursors in
the body or a header, Stripe's last-item cursor, next URLs, page numbers and offsets.
"""

from apiroute.pagination.async_paginated import AsyncPaginated
from apiroute.pagination.cursor import Cursor
from apiroute.pagination.item_cursor import ItemCursor
from apiroute.pagination.next_request import NextRequest
from apiroute.pagination.next_url import NextUrl
from apiroute.pagination.offset import Offset
from apiroute.pagination.page import Page
from apiroute.pagination.page_number import PageNumber
from apiroute.pagination.paginated import Paginated
from apiroute.pagination.strategy import Strategy

__all__ = [
    "AsyncPaginated",
    "Cursor",
    "ItemCursor",
    "NextRequest",
    "NextUrl",
    "Offset",
    "Page",
    "PageNumber",
    "Paginated",
    "Strategy",
]
