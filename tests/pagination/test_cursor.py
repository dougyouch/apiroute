import pytest

from apiroute.pagination import Cursor, NextRequest
from tests.pagination.pages import page


def test_token_from_a_body_path():
    strategy = Cursor("cursor", token="response_metadata.next_cursor", items="members")
    data = {"members": [1], "response_metadata": {"next_cursor": "dXNlcg=="}}
    assert strategy.items(page(data)) == [1]
    assert strategy.next(page(data)) == NextRequest(query={"cursor": "dXNlcg=="})


@pytest.mark.parametrize("data", [{}, {"next_cursor": None}, {"next_cursor": ""}])
def test_stops_on_a_missing_null_or_empty_token(data):
    assert Cursor("cursor").next(page(data)) is None


def test_token_from_a_header():
    strategy = Cursor("page_token", header="X-Next-Token")
    assert strategy.next(page([], headers={"X-Next-Token": "t2"})) == NextRequest(
        query={"page_token": "t2"}
    )
    assert strategy.next(page([])) is None


def test_token_sent_in_the_body():
    strategy = Cursor("cursor", location="body")
    assert strategy.next(page({"next_cursor": "c"})) == NextRequest(body={"cursor": "c"})


def test_rejects_other_locations():
    with pytest.raises(ValueError, match="location"):
        Cursor("cursor", location="header")
