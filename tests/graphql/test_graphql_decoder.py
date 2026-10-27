import logging

import httpx
import pytest

from apiroute import UnexpectedResponse
from apiroute.graphql import GraphQLDecoder, GraphQLError

REQUEST = httpx.Request("POST", "https://u:p@api.test/graphql?key=secret")


def response(status=200, **kwargs):
    return httpx.Response(status, request=REQUEST, **kwargs)


def test_returns_data():
    decoder = GraphQLDecoder("Viewer")
    assert decoder(response(json={"data": {"viewer": {"login": "a"}}})) == {
        "viewer": {"login": "a"}
    }


def test_unwraps_a_dotted_path():
    decoder = GraphQLDecoder("Repo", "viewer.repositories.nodes")
    body = {"data": {"viewer": {"repositories": {"nodes": [{"name": "x"}]}}}}
    assert decoder(response(json=body)) == [{"name": "x"}]


def test_a_null_or_missing_step_returns_none():
    decoder = GraphQLDecoder("Repo", "repository.owner")
    assert decoder(response(json={"data": {"repository": None}})) is None
    assert decoder(response(json={"data": {}})) is None


def test_errors_raise_graphql_error_with_partial_data():
    body = {
        "data": {"viewer": None},
        "errors": [
            {"message": "Not allowed", "path": ["viewer"], "extensions": {"code": "FORBIDDEN"}}
        ],
    }
    with pytest.raises(GraphQLError) as caught:
        GraphQLDecoder("Viewer")(response(json=body))
    error = caught.value
    assert str(error) == "Viewer: Not allowed (at viewer)"
    assert error.codes == ["FORBIDDEN"]
    assert error.data == {"viewer": None}
    assert error.errors == body["errors"]
    assert error.response.status_code == 200


def test_the_message_counts_further_errors():
    body = {"errors": [{"message": "a"}, {"message": "b"}, {"message": "c"}]}
    with pytest.raises(GraphQLError, match=r"^A: a and 2 more errors$"):
        GraphQLDecoder("A")(response(json=body))


def test_errors_on_a_400_raise_graphql_error():
    with pytest.raises(GraphQLError, match="Syntax Error"):
        GraphQLDecoder("A")(response(400, json={"errors": [{"message": "Syntax Error"}]}))


def test_a_400_without_errors_is_unexpected():
    with pytest.raises(UnexpectedResponse) as caught:
        GraphQLDecoder("A")(response(400, json={"data": None}))
    assert "secret" not in str(caught.value)
    assert "u:p" not in str(caught.value)
    assert "unexpected status 400" in str(caught.value)


@pytest.mark.parametrize(
    "kwargs",
    [{"text": "<html>"}, {"json": [1]}, {"json": {"message": "hi"}}, {"json": {"errors": "x"}}],
)
def test_a_body_that_isnt_graphql_is_unexpected(kwargs):
    with pytest.raises(UnexpectedResponse, match="not a GraphQL response"):
        GraphQLDecoder("A")(response(**kwargs))


def test_partial_returns_data_and_logs_the_errors(caplog):
    body = {"data": {"a": 1, "b": None}, "errors": [{"message": "b failed", "path": ["b"]}]}
    with caplog.at_level(logging.WARNING):
        assert GraphQLDecoder("A", errors="partial")(response(json=body)) == {"a": 1, "b": None}
    assert "A returned partial data: b failed (at b)" in caplog.text


def test_partial_still_raises_without_data():
    with pytest.raises(GraphQLError):
        GraphQLDecoder("A", errors="partial")(
            response(json={"data": None, "errors": [{"message": "x"}]})
        )


def test_rejects_an_unknown_error_mode():
    with pytest.raises(ValueError, match="errors must be one of"):
        GraphQLDecoder("A", errors="ignore")
