from apiroute.pagination import NextRequest, Offset
from tests.pagination.pages import page


def test_moves_past_the_items_received():
    assert Offset().next(page([1, 2], items=[1, 2])) == NextRequest(query={"offset": 2})
    sent = page([1, 2], url="https://api.test/items?offset=4", items=[1, 2])
    assert Offset().next(sent) == NextRequest(query={"offset": 6})


def test_stops_at_an_empty_page():
    assert Offset().next(page([])) is None


def test_stops_at_the_total():
    strategy = Offset(total="total", items="hits")
    data = {"hits": [1], "total": 5}
    assert strategy.next(page(data, url="https://api.test/i?offset=4", items=[1])) is None
    sent = page(data, url="https://api.test/i?offset=2&limit=2", items=[1])
    assert strategy.next(sent) == NextRequest(query={"offset": 3})


def test_a_short_page_is_last_only_with_a_sent_limit():
    assert Offset().next(page([1], url="https://api.test/i?limit=2", items=[1])) is None
    assert Offset().next(page([1], items=[1])) == NextRequest(query={"offset": 1})
