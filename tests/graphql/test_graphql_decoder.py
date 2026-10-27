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


def test_codes_fall_back_to_a_top_level_type_as_github_sends():
    body = {
        "data": {"repository": None},
        "errors": [
            {"type": "NOT_FOUND", "path": ["repository"], "message": "Could not resolve"},
            {"message": "x", "extensions": {"code": "THROTTLED"}, "type": "IGNORED"},
        ],
    }
    with pytest.raises(GraphQLError) as caught:
        GraphQLDecoder("Repo")(response(json=body))
    assert caught.value.codes == ["NOT_FOUND", "THROTTLED"]


@pytest.mark.parametrize(
    "body, kind",
    [
        ({"errors": [{"message": "PersistedQueryNotFound"}]}, "not_found"),
        (
            {"errors": [{"message": "x", "extensions": {"code": "PERSISTED_QUERY_NOT_FOUND"}}]},
            "not_found",
        ),
        ({"errors": [{"message": "PersistedQueryNotSupported"}]}, "not_supported"),
        ({"errors": [{"message": "A query attribute must be specified"}]}, "not_supported"),
    ],
)
def test_persisted_replies_on_a_hash_only_request(body, kind):
    from apiroute.graphql.persisted_query_reply import PersistedQueryReply

    with pytest.raises(PersistedQueryReply) as caught:
        GraphQLDecoder("A").for_persisted_replies()(response(json=body))
    assert caught.value.kind == kind
    assert isinstance(caught.value, GraphQLError)


def test_an_executed_query_error_isnt_a_persisted_reply():
    from apiroute.graphql.persisted_query_reply import PersistedQueryReply

    body = {"data": None, "errors": [{"message": "Forbidden"}]}
    with pytest.raises(GraphQLError) as caught:
        GraphQLDecoder("A").for_persisted_replies()(response(json=body))
    assert not isinstance(caught.value, PersistedQueryReply)


def test_ordinary_decoders_never_raise_persisted_replies():
    from apiroute.graphql.persisted_query_reply import PersistedQueryReply

    with pytest.raises(GraphQLError) as caught:
        GraphQLDecoder("A")(response(json={"errors": [{"message": "PersistedQueryNotFound"}]}))
    assert not isinstance(caught.value, PersistedQueryReply)
