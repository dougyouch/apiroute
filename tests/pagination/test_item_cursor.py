import pytest

from apiroute.pagination import ItemCursor, NextRequest
from tests.pagination.pages import page


def test_continues_after_the_last_item():
    data = {"data": [{"id": "a"}, {"id": "b"}], "has_more": True}
    strategy = ItemCursor()
    items = strategy.items(page(data))
    assert strategy.next(page(data, items=items)) == NextRequest(query={"starting_after": "b"})


def test_stops_when_there_is_no_more():
    last = page({"data": [{"id": "a"}], "has_more": False}, items=[{"id": "a"}])
    assert ItemCursor().next(last) is None


def test_custom_field_and_flag():
    strategy = ItemCursor("after", field="key", has_more="meta.more", items="rows")
    data = {"rows": [{"key": 5}], "meta": {"more": True}}
    assert strategy.next(page(data, items=data["rows"])) == NextRequest(query={"after": 5})


def test_an_empty_page_with_more_is_an_error():
    with pytest.raises(ValueError, match="has_more is true on an empty page"):
        ItemCursor().next(page({"data": [], "has_more": True}))


def test_a_last_item_without_the_field_is_an_error():
    with pytest.raises(ValueError, match="no 'id'"):
        ItemCursor().next(page({"has_more": True}, items=[{"name": "x"}]))
