import json

from apiroute.graphql import GraphQLBody


def test_sends_the_query_operation_name_and_variables():
    content, content_type = GraphQLBody("query A($x: Int) { a }", "A")(None, {"x": 1})
    assert content_type == "application/json"
    assert json.loads(content) == {
        "query": "query A($x: Int) { a }",
        "operationName": "A",
        "variables": {"x": 1},
    }


def test_none_variables_are_left_out():
    content, _ = GraphQLBody("q", "A")(None, {"x": None, "y": False, "z": 0})
    assert json.loads(content)["variables"] == {"y": False, "z": 0}


def test_an_anonymous_operation_sends_no_operation_name():
    content, _ = GraphQLBody("{ a }", None)(None, None)
    assert json.loads(content) == {"query": "{ a }", "variables": {}}


def test_encodes_without_variables():
    assert GraphQLBody.encodes_empty is True
