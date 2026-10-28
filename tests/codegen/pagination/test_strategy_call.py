import pytest

from apiroute.codegen.pagination.strategy_call import StrategyCall


def test_names_the_class_and_its_items_path():
    call = StrategyCall("item_cursor", {})
    assert (call.class_name, call.items) == ("ItemCursor", "data")
    assert StrategyCall("next_url", {"items": "results"}).items == "results"
    assert StrategyCall("page", {}).class_name == "PageNumber"


@pytest.mark.parametrize(
    "kind, arguments, message",
    [
        ("pages", {}, "unknown type 'pages'"),
        ("offset", {"totl": "total"}, "offset: got an unexpected keyword argument 'totl'"),
        ("cursor", {}, "cursor: missing a required argument: 'param'"),
        ("cursor", {"param": "c", "location": "header"}, "location must be one of"),
    ],
)
def test_bad_strategies_are_refused(kind, arguments, message):
    with pytest.raises(ValueError, match=message):
        StrategyCall(kind, arguments)
