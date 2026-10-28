from apiroute.pagination import NextRequest, PageNumber
from tests.pagination.pages import page


def test_asks_for_the_next_number():
    assert PageNumber().next(page([1], items=[1])) == NextRequest(query={"page": 2})
    sent = page([1], url="https://api.test/items?page=4", items=[1])
    assert PageNumber().next(sent) == NextRequest(query={"page": 5})


def test_stops_at_an_empty_page():
    assert PageNumber().next(page([])) is None


def test_stops_at_the_total():
    strategy = PageNumber(total_pages="meta.pages", items="data")
    at = "https://api.test/items?page={}".format
    data = {"data": [1], "meta": {"pages": 3}}
    assert strategy.next(page(data, url=at(2), items=[1])) == NextRequest(query={"page": 3})
    assert strategy.next(page(data, url=at(3), items=[1])) is None


def test_a_zero_based_total():
    strategy = PageNumber(start=0, total_pages="pages", items="data")
    data = {"data": [1], "pages": 2}
    assert strategy.next(page(data, items=[1])) == NextRequest(query={"page": 1})
    assert strategy.next(page(data, url="https://api.test/i?page=1", items=[1])) is None


def test_a_short_page_is_last_only_with_a_sent_size():
    strategy = PageNumber(size="per_page")
    short = page([1], url="https://api.test/items?per_page=2&page=3", items=[1])
    assert strategy.next(short) is None
    assert strategy.next(page([1], url="https://api.test/items?page=3", items=[1])) is not None


def test_a_total_wins_over_a_short_page():
    strategy = PageNumber(size="per_page", total_pages="pages", items="data")
    data = {"data": [1], "pages": 9}
    sent = page(data, url="https://api.test/items?per_page=2", items=[1])
    assert strategy.next(sent) == NextRequest(query={"page": 2})
