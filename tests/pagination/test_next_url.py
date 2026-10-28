from apiroute.pagination import NextRequest, NextUrl
from tests.pagination.pages import page

LINK = (
    '<https://api.github.com/repositories/1/issues?page=2>; rel="next", '
    '<https://api.github.com/repositories/1/issues?page=5>; rel="last"'
)


def test_follows_the_link_header():
    assert NextUrl().next(page([], headers={"Link": LINK})) == NextRequest(
        url="https://api.github.com/repositories/1/issues?page=2"
    )


def test_another_rel():
    assert NextUrl(link="last").next(page([], headers={"Link": LINK})).url.endswith("page=5")


def test_stops_without_a_next_link():
    last = '<https://api.github.com/repositories/1/issues?page=1>; rel="first"'
    assert NextUrl().next(page([], headers={"Link": last})) is None
    assert NextUrl().next(page([])) is None


def test_a_url_in_the_body():
    strategy = NextUrl(path="next", items="results")
    data = {"results": [1], "next": "https://api.test/items?cursor=2"}
    assert strategy.items(page(data)) == [1]
    assert strategy.next(page(data)) == NextRequest(url="https://api.test/items?cursor=2")
    assert strategy.next(page({"results": [], "next": None})) is None
