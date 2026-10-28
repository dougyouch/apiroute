from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import islice

import httpx
import pytest

from apiroute import Client, Query, Retries, RouteDefinitionError, UnexpectedResponse, route
from apiroute.pagination import Cursor, ItemCursor, NextRequest, NextUrl, Offset, Page, PageNumber
from apiroute.testing import MockTransport


@dataclass
class Customer:
    id: str


def stripe_page(ids, more):
    return httpx.Response(200, json={"data": [{"id": i} for i in ids], "has_more": more})


class Api(Client):
    base_url = "https://api.test/v1"
    headers = {"Authorization": "Bearer k"}
    retries = Retries(attempts=2, sleep=0)
    idempotency_key = "Idempotency-Key"

    def should_retry(self, error, attempt):
        return isinstance(error, UnexpectedResponse) and error.status_code == 503

    @route("GET", "/customers", paginate=ItemCursor())
    def customers(
        self, limit: Query = None, status: Query = None, starting_after: Query = None
    ) -> Iterator[Customer]: ...

    raw_customers = route("GET", "/customers", paginate=ItemCursor())

    @route("GET", "/issues", paginate=NextUrl())
    def issues(self) -> Iterator[dict]: ...

    @route("GET", "/items", paginate=NextUrl(path="next", items="results"))
    def items(self) -> Iterator[dict]: ...

    @route("GET", "/pages", paginate=PageNumber(total_pages="meta.pages", items="data"))
    def pages(self) -> Iterator[int]: ...

    @route("GET", "/hits", paginate=Offset(total="total", items="hits"))
    def hits(self, limit: Query) -> Iterator[int]: ...


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def api(mock):
    return Api(transport=mock, async_transport=mock.aio)


def test_three_pages(api, mock):
    mock.respond(stripe_page("ab", True), stripe_page("cd", True), stripe_page("e", False))
    assert [c.id for c in api.customers()] == list("abcde")
    assert [call.params.get("starting_after") for call in mock.calls] == [None, "b", "d"]
    assert all(call.headers["Authorization"] == "Bearer k" for call in mock.calls)


def test_lazy_paging(api, mock):
    mock.respond(stripe_page("ab", True), stripe_page("cd", False))
    customers = api.customers()
    assert mock.calls == []
    assert next(customers).id == "a"
    assert len(mock.calls) == 1
    assert [c.id for c in islice(customers, 1)] == ["b"]
    assert len(mock.calls) == 1


def test_filters_stay_on_every_page(api, mock):
    mock.respond(stripe_page("a", True), stripe_page("b", False))
    list(api.customers(limit=2, status="open"))
    assert [(c.params["limit"], c.params["status"]) for c in mock.calls] == [("2", "open")] * 2


def test_starting_from_a_cursor(api, mock):
    mock.respond(stripe_page("x", False))
    list(api.customers(starting_after="cus_9"))
    assert mock.last.params["starting_after"] == "cus_9"


def test_a_generated_signature_yields_dicts(api, mock):
    mock.respond(stripe_page("a", True), stripe_page("b", False))
    assert list(api.raw_customers()) == [{"id": "a"}, {"id": "b"}]


def test_an_error_on_a_later_page(api, mock):
    mock.respond(stripe_page("a", True), httpx.Response(500))
    customers = api.customers()
    assert next(customers).id == "a"
    with pytest.raises(UnexpectedResponse):
        next(customers)


def test_retries_cover_each_page(api, mock):
    mock.respond(stripe_page("a", True), httpx.Response(503), stripe_page("b", False))
    assert [c.id for c in api.customers()] == ["a", "b"]
    assert len(mock.calls) == 3


def test_a_post_search_pages_with_its_body_and_a_key_per_page(mock):
    class Search(Client):
        base_url = "https://api.test"
        idempotency_key = "Idempotency-Key"

        @route(
            "POST",
            "/search",
            body={"query": "{query}"},
            paginate=Cursor("cursor", location="body", items="items"),
        )
        def search(self, query: str) -> Iterator[int]: ...

    mock.respond(
        httpx.Response(200, json={"items": [1], "next_cursor": "t"}),
        httpx.Response(200, json={"items": [2], "next_cursor": None}),
    )
    assert list(Search(transport=mock).search("x")) == [1, 2]
    assert [call.json() for call in mock.calls] == [{"query": "x"}, {"query": "x", "cursor": "t"}]
    keys = [call.headers["Idempotency-Key"] for call in mock.calls]
    assert len(set(keys)) == 2


def test_the_link_header(api, mock):
    link = (
        '<https://api.test/v1/issues?page=2>; rel="next", '
        '<https://api.test/v1/issues?page=5>; rel="last"'
    )
    mock.respond(
        httpx.Response(200, json=[{"n": 1}], headers={"Link": link}),
        httpx.Response(200, json=[{"n": 2}]),
    )
    assert list(api.issues()) == [{"n": 1}, {"n": 2}]
    assert str(mock.last.url) == "https://api.test/v1/issues?page=2"
    assert mock.last.headers["Authorization"] == "Bearer k"


def test_a_next_url_on_another_host_is_refused(api, mock):
    link = '<https://evil.test/steal?page=2>; rel="next"'
    mock.respond(httpx.Response(200, json=[{"n": 1}], headers={"Link": link}))
    issues = api.issues()
    assert next(issues) == {"n": 1}
    with pytest.raises(ValueError, match="issues: the next page's URL is on https://evil.test"):
        next(issues)
    assert len(mock.calls) == 1


def test_a_relative_next_url(api, mock):
    mock.respond(
        httpx.Response(200, json={"results": [1], "next": "/v1/items?cursor=2"}),
        httpx.Response(200, json={"results": [2], "next": None}),
    )
    assert list(api.items()) == [1, 2]
    assert str(mock.last.url) == "https://api.test/v1/items?cursor=2"


def test_pages_with_a_total(api, mock):
    def answer(request):
        return httpx.Response(
            200, json={"data": [int(request.url.params.get("page", 1))], "meta": {"pages": 3}}
        )

    mock.respond(answer, answer, answer, answer)
    assert list(api.pages()) == [1, 2, 3]
    assert len(mock.calls) == 3


def test_offsets(api, mock):
    def answer(request):
        offset = int(request.url.params.get("offset", 0))
        return httpx.Response(200, json={"hits": list(range(5))[offset : offset + 2], "total": 5})

    mock.respond(answer, answer, answer, answer)
    assert list(api.hits(limit=2)) == [0, 1, 2, 3, 4]
    assert [call.params.get("offset") for call in mock.calls] == [None, "2", "4"]


def test_a_repeated_cursor(mock):
    class Slack(Client):
        base_url = "https://slack.test"
        users = route("GET", "/users", paginate=Cursor("cursor", items="members"))

    page = httpx.Response(200, json={"members": [1], "next_cursor": "c1"})
    mock.respond(page, page)
    with pytest.raises(ValueError, match="users: the next page's request is the same"):
        list(Slack(transport=mock).users())


def test_items_not_a_list(api, mock):
    mock.respond(httpx.Response(200, json={"data": {}, "has_more": False}))
    with pytest.raises(ValueError, match="customers: page 1: items 'data' is a dict"):
        list(api.customers())


def test_whole_pages(api, mock):
    mock.respond(stripe_page("ab", True), stripe_page("c", False))
    pages = list(api.customers().pages())
    assert [p.index for p in pages] == [0, 1]
    assert [p.items for p in pages] == [[{"id": "a"}, {"id": "b"}], [{"id": "c"}]]
    assert pages[1].request == NextRequest(query={"starting_after": "b"})
    assert pages[1].data["has_more"] is False
    assert pages[0].response.status_code == 200


def test_a_custom_strategy(mock):
    class Since:
        def items(self, page: Page) -> list:
            return page.data["events"]

        def next(self, page: Page) -> NextRequest | None:
            if page.response.headers.get("X-Done") == "1":
                return None
            return NextRequest(query={"since": page.data["last_seen"]})

    class Feed(Client):
        base_url = "https://feed.test"
        events = route("GET", "/events", paginate=Since())

    mock.respond(
        httpx.Response(200, json={"events": [1], "last_seen": 10}),
        httpx.Response(200, json={"events": [2], "last_seen": 20}, headers={"X-Done": "1"}),
    )
    assert list(Feed(transport=mock).events()) == [1, 2]
    assert [call.params.get("since") for call in mock.calls] == [None, "10"]


def test_async_for(api, mock):
    mock.respond(stripe_page("ab", True), stripe_page("c", False))

    async def collect():
        return [c.id async for c in api.aio.customers(limit=2)]

    assert asyncio.run(collect()) == ["a", "b", "c"]
    assert len(mock.calls) == 2


def test_async_pages(api, mock):
    mock.respond(stripe_page("a", True), stripe_page("b", False))

    async def collect():
        return [page.items async for page in api.aio.customers().pages()]

    assert asyncio.run(collect()) == [[{"id": "a"}], [{"id": "b"}]]


def test_model_converts_items(mock):
    class Typed(Client):
        base_url = "https://api.test"
        customers = route("GET", "/customers", paginate=ItemCursor(), model=Customer)

    mock.respond(stripe_page("a", False))
    assert list(Typed(transport=mock).customers()) == [Customer("a")]


def test_wrong_arguments_fail_on_the_call(api):
    with pytest.raises(TypeError):
        api.customers(nope=1)


@pytest.mark.parametrize(
    "options, message",
    [
        ({"returns": "text"}, "reads JSON pages"),
        ({"stream": "iter"}, "reads JSON pages"),
        ({"decoder": lambda response: None}, "decoder="),
    ],
)
def test_options_paging_cannot_take(options, message):
    with pytest.raises(RouteDefinitionError, match=message):

        class Bad(Client):
            base_url = "https://api.test"
            items = route("GET", "/items", paginate=ItemCursor(), **options)


def test_a_strategy_must_have_items_and_next():
    with pytest.raises(RouteDefinitionError, match=r"items\(page\) and next\(page\)"):

        class Bad(Client):
            base_url = "https://api.test"
            items = route("GET", "/items", paginate="data")
