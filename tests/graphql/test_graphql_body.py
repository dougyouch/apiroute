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


def test_files_make_a_multipart_request_in_the_spec_order():
    from apiroute.graphql import Upload
    from tests.graphql.multipart import parse_multipart

    body = GraphQLBody("mutation U($file: Upload!, $note: String) { u }", "U")
    content, content_type = body(None, {"file": Upload(b"hello", "a.txt"), "note": None})
    assert content_type.startswith("multipart/form-data; boundary=")
    parts = parse_multipart(content, content_type)
    assert [name for name, *_ in parts] == ["operations", "map", "0"]
    assert json.loads(parts[0][3]) == {
        "query": "mutation U($file: Upload!, $note: String) { u }",
        "operationName": "U",
        "variables": {"file": None},
    }
    assert json.loads(parts[1][3]) == {"0": ["variables.file"]}
    assert parts[2] == ("0", "a.txt", "text/plain", b"hello")


def test_a_persisted_upload_carries_the_extensions_in_operations():
    from apiroute.graphql import Upload
    from tests.graphql.multipart import parse_multipart

    body = GraphQLBody("mutation U($f: Upload!) { u }", "U", persisted="hash")
    operations = json.loads(parse_multipart(*body(None, {"f": Upload(b"x")}))[0][3])
    assert "query" not in operations
    assert operations["extensions"]["persistedQuery"]["sha256Hash"] == body.sha256
    assert operations["variables"] == {"f": None}
