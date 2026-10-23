from apiroute.argument_targets import Body, Header, Query


def test_query_defaults_to_the_parameter_name():
    assert Query().key_for("sort") == "sort"
    assert Query("sort_by").key_for("sort") == "sort_by"


def test_header_name_from_the_parameter():
    assert Header().key_for("trace_id") == "Trace-Id"
    assert Header("X-Trace").key_for("trace_id") == "X-Trace"


def test_locations():
    assert (Query.location, Header.location, Body.location) == ("query", "header", "body")
