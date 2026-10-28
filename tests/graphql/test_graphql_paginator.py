import asyncio
import inspect

import pytest

from apiroute.graphql.graphql_paginator import GraphQLPaginator
from apiroute.item_type import item_type


def connection(items, cursor=None, more=False, key="nodes"):
    page_info = {"hasNextPage": more, "endCursor": cursor}
    if key == "edges":
        return {"pageInfo": page_info, "edges": [{"node": item} for item in items]}
    return {"pageInfo": page_info, "nodes": items}


class Pages:
    """A fake route answering pages of {"repo": {"issues": ...}} in turn, recording the cursor
    each page was asked for (as page_call(cursor) would set it)."""

    def __init__(self, *connections):
        self._connections = list(connections)
        self.calls = []

    def page_call(self, cursor):
        def call(*, owner):
            self.calls.append(cursor)
            return {"repo": {"issues": self._connections.pop(0)}}

        call.__signature__ = inspect.Signature(
            [inspect.Parameter("owner", inspect.Parameter.KEYWORD_ONLY)]
        )
        return call


def paged(pages, converter=None):
    return GraphQLPaginator("Issues", "repo.issues", converter).wrap(pages.page_call, False)


def test_follows_end_cursors_across_pages():
    pages = Pages(connection([1, 2], "c1", True), connection([3], "c2", True), connection([4]))
    assert list(paged(pages)(owner="o")) == [1, 2, 3, 4]
    assert pages.calls == [None, "c1", "c2"]


def test_requests_pages_only_as_iteration_reaches_them():
    pages = Pages(connection([1, 2], "c1", True), connection([3]))
    items = paged(pages)(owner="o")
    assert pages.calls == []
    assert next(items) == 1
    assert pages.calls == [None]


def test_edges():
    pages = Pages(connection(["a"], "c6", True, key="edges"), connection(["b"], key="edges"))
    assert list(paged(pages)(owner="o")) == ["a", "b"]
    assert pages.calls == [None, "c6"]


def test_wrong_arguments_fail_on_the_call():
    with pytest.raises(TypeError):
        paged(Pages())(nope=1)


def test_null_items_stay_null_and_null_edges_give_none():
    pages = Pages(
        {"pageInfo": {"hasNextPage": False, "endCursor": None}, "edges": [None, {"node": 1}]}
    )
    assert list(paged(pages)(owner="o")) == [None, 1]


def test_a_null_connection_yields_nothing():
    pages = Pages(None)
    pages._connections = [None]
    assert list(paged(pages)(owner="o")) == []


def test_items_are_converted():
    class Doubling:
        def convert(self, item):
            return item * 2

    assert list(paged(Pages(connection([1, None, 3])), Doubling())(owner="o")) == [2, None, 6]


@pytest.mark.parametrize(
    "page, message",
    [
        (
            {"nodes": [1]},
            r"needs the operation to select pageInfo \{ hasNextPage endCursor \} on repo.issues",
        ),
        ({"pageInfo": {"hasNextPage": False}, "nodes": [1]}, "pageInfo"),
        (
            {"pageInfo": {"hasNextPage": False, "endCursor": None}},
            r"selects neither nodes nor edges \{ node \}",
        ),
        (connection([1], None, True), "hasNextPage with no endCursor; paging would never end"),
    ],
)
def test_pages_that_cant_be_followed(page, message):
    with pytest.raises(ValueError, match=f"^Issues: .*{message}"):
        list(paged(Pages(page))(owner="o"))


def test_a_repeated_cursor_stops_instead_of_looping():
    pages = Pages(connection([1], "c1", True), connection([2], "c1", True))
    items = paged(pages)(owner="o")
    with pytest.raises(ValueError, match=r"the same endCursor \('c1'\) again"):
        list(items)


def test_async_pages():
    pages = Pages(connection([1], "c1", True), connection([2]))

    def async_page_call(cursor):
        call = pages.page_call(cursor)

        async def awaitable(**kwargs):
            return call(**kwargs)

        awaitable.__signature__ = call.__signature__
        return awaitable

    wrapped = GraphQLPaginator("Issues", "repo.issues").wrap(async_page_call, True)

    async def collect():
        return [item async for item in wrapped(owner="o")]

    assert asyncio.run(collect()) == [1, 2]
    assert pages.calls == [None, "c1"]


def test_the_wrapper_keeps_the_signature():
    pages = Pages()
    assert inspect.signature(paged(pages)) == pages.page_call(None).__signature__


def test_item_type():
    from collections.abc import AsyncIterator, Generator, Iterable, Iterator

    assert [item_type(t) for t in (Iterator[int], Iterable[str], AsyncIterator[bytes])] == [
        int,
        str,
        bytes,
    ]
    assert item_type(Generator[float, None, None]) is float
    assert [item_type(t) for t in (list[int], dict, None)] == [None, None, None]
