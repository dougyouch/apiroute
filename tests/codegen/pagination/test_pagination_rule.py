import pytest

from apiroute.codegen.pagination.operation_facts import OperationFacts
from apiroute.codegen.pagination.pagination_rule import PaginationRule

STRIPE = {
    "has_parameter": ["starting_after"],
    "response": {"has": ["data", "has_more"]},
    "paginate": {"type": "item_cursor"},
}


def facts(operation_id="GetCustomers", method="GET", parameters=(), array=False, properties=()):
    return OperationFacts(operation_id, method, frozenset(parameters), array, frozenset(properties))


def test_matches_on_parameters_and_response_properties():
    rule = PaginationRule(STRIPE, "rule 1")
    stripe_list = facts(parameters=["limit", "starting_after"], properties=["data", "has_more"])
    assert rule.matches(stripe_list)
    assert not rule.matches(stripe_list._replace(method="POST"))
    assert not rule.matches(stripe_list._replace(parameters=frozenset({"limit"})))
    assert not rule.matches(stripe_list._replace(properties=frozenset({"data"})))


def test_matches_operation_ids_by_glob_and_methods():
    rule = PaginationRule(
        {"operations": ["Search*"], "method": ["get", "POST"], "paginate": {"type": "offset"}},
        "rule 1",
    )
    assert rule.matches(facts("SearchHits", method="POST"))
    assert not rule.matches(facts("ListHits"))


def test_an_array_response():
    rule = PaginationRule({"response": "array", "paginate": {"type": "next_url"}}, "rule 1")
    assert rule.matches(facts(array=True))
    assert not rule.matches(facts(properties=["data"]))


def test_a_named_rule_is_labelled_by_its_name():
    assert PaginationRule({**STRIPE, "name": "Stripe"}, "rule 1").label == "rule 1 (Stripe)"


@pytest.mark.parametrize(
    "raw, message",
    [
        ([], "expected an object"),
        ({"paginate": {"type": "offset"}, "methods": ["GET"]}, "unknown keys methods"),
        ({}, "paginate needs an object with a type"),
        ({"paginate": {"type": "nope"}}, "rule 1: unknown type 'nope'"),
        ({"response": "object", "paginate": {"type": "offset"}}, "response is"),
        ({"has_parameter": [1], "paginate": {"type": "offset"}}, "has_parameter is a name"),
    ],
)
def test_bad_rules_name_the_rule(raw, message):
    with pytest.raises(ValueError, match=message):
        PaginationRule(raw, "rule 1")
