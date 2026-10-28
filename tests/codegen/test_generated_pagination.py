import asyncio

import httpx
import pytest

from apiroute.testing import MockTransport
from tests.conftest import needs_pydantic


@pytest.fixture
def paging(generate):
    return generate("paging.yaml", client_name="PagingApi", pagination="paging.rules.yaml")


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def api(paging, mock):
    return paging.PagingApi(transport=mock, async_transport=mock.aio)


def customers(*ids, more):
    return httpx.Response(200, json={"data": [{"id": i} for i in ids], "has_more": more})


def test_the_one_page_method_is_unchanged(api, mock):
    mock.respond(customers("a", more=True))
    assert api.customers.get_customers(limit=1) == {"data": [{"id": "a"}], "has_more": True}


def test_the_all_method_pages_with_the_callers_arguments(api, mock):
    mock.respond(customers("a", more=True), customers("b", more=False))
    assert list(api.customers.get_customers_all(limit=1)) == [{"id": "a"}, {"id": "b"}]
    assert [(c.params.get("starting_after"), c.params["limit"]) for c in mock.calls] == [
        (None, "1"),
        ("a", "1"),
    ]
    assert all(call.operation == "GetCustomers" for call in mock.calls)


def test_link_headers_and_offsets(api, mock):
    link = '<https://api.paging.test/repositories/1/issues?page=2>; rel="next"'
    mock.respond(
        httpx.Response(200, json=[{"number": 1}], headers={"Link": link}),
        httpx.Response(200, json=[{"number": 2}]),
        httpx.Response(200, json={"hits": [{"name": "x"}], "total": 1}),
    )
    assert [i["number"] for i in api.issues.list_for_repo_all("o", "r")] == [1, 2]
    assert list(api.search.hits_all(q="x")) == [{"name": "x"}]


@needs_pydantic
def test_typed_items(api, paging, mock):
    mock.respond(customers("a", more=True), customers("b", more=False))
    items = list(api.customers.models.get_customers_all())
    assert [type(i).__name__ for i in items] == ["Customer", "Customer"]
    assert [i.id for i in items] == ["a", "b"]


@needs_pydantic
def test_typed_items_through_aio(api, mock):
    mock.respond(customers("a", more=True), customers("b", more=False))

    async def collect():
        return [c.id async for c in api.customers.models.aio.get_customers_all()]

    assert asyncio.run(collect()) == ["a", "b"]


def test_existing_fixtures_get_no_all_methods(generate):
    shop = generate("shop.yaml", models=False)
    assert not any(name.endswith("_all") for name in dir(shop.ShopApi))
