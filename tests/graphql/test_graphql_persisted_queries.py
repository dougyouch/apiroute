import asyncio
import hashlib
import json

import httpx
import pytest

from apiroute import Client, GraphQLError, graphql_route
from apiroute.graphql import GraphQLBody
from apiroute.testing import MockTransport, graphql_response

VIEWER = "query Viewer { viewer { login } }"
SHA = hashlib.sha256(VIEWER.encode()).hexdigest()
NOT_FOUND = graphql_response(
    errors=[
        {"message": "PersistedQueryNotFound", "extensions": {"code": "PERSISTED_QUERY_NOT_FOUND"}}
    ]
)
NOT_SUPPORTED = graphql_response(
    errors=[
        {
            "message": "PersistedQueryNotSupported",
            "extensions": {"code": "PERSISTED_QUERY_NOT_SUPPORTED"},
        }
    ]
)
DATA = graphql_response(data={"viewer": {"login": "octo"}})
EXTENSION = {"persistedQuery": {"version": 1, "sha256Hash": SHA}}


class Hub(Client):
    base_url = "https://api.hub.test"
    viewer = graphql_route(VIEWER, persisted=True, data="viewer.login")


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def hub(mock):
    return Hub(transport=mock, async_transport=mock.aio)


def bodies(mock):
    return [call.json() for call in mock.calls]


def test_the_body_modes():
    def encode(mode):
        return json.loads(GraphQLBody(VIEWER, "Viewer", mode)(None, {"x": 1, "y": None})[0])

    assert encode(None) == {"query": VIEWER, "operationName": "Viewer", "variables": {"x": 1}}
    assert encode("hash") == {
        "operationName": "Viewer",
        "variables": {"x": 1},
        "extensions": EXTENSION,
    }
    assert encode("register") == {
        "query": VIEWER,
        "operationName": "Viewer",
        "variables": {"x": 1},
        "extensions": EXTENSION,
    }
    with pytest.raises(ValueError, match="persisted must be one of"):
        GraphQLBody(VIEWER, "Viewer", "always")


def test_a_cached_query_is_one_hash_only_request(hub, mock):
    mock.respond(DATA)
    assert hub.viewer() == "octo"
    assert bodies(mock) == [{"operationName": "Viewer", "variables": {}, "extensions": EXTENSION}]


def test_a_miss_registers_the_document_and_the_next_call_is_hash_only(hub, mock):
    mock.respond(NOT_FOUND, DATA, DATA)
    assert hub.viewer() == "octo"
    first, second = bodies(mock)
    assert "query" not in first
    assert second == {
        "query": VIEWER,
        "operationName": "Viewer",
        "variables": {},
        "extensions": EXTENSION,
    }
    assert hub.viewer() == "octo"
    assert "query" not in bodies(mock)[2]


def test_a_miss_on_http_400_by_message_only(hub, mock):
    mock.respond(
        httpx.Response(400, json={"errors": [{"message": "PersistedQueryNotFound"}]}), DATA
    )
    assert hub.viewer() == "octo"
    assert len(mock.calls) == 2


def test_a_real_error_after_registering_raises(hub, mock):
    mock.respond(NOT_FOUND, graphql_response(errors=[{"message": "Forbidden"}]))
    with pytest.raises(GraphQLError, match="Forbidden"):
        hub.viewer()


def test_other_errors_raise_without_another_request(hub, mock):
    mock.respond(graphql_response(errors=[{"message": "Cannot query field"}]))
    with pytest.raises(GraphQLError, match="Cannot query field"):
        hub.viewer()
    assert len(mock.calls) == 1


def test_an_unsupported_server_gets_full_documents_from_then_on(hub, mock):
    mock.respond(NOT_SUPPORTED, DATA, DATA)
    assert hub.viewer() == "octo"
    assert hub.viewer() == "octo"
    first, second, third = bodies(mock)
    assert "query" not in first
    assert second == third == {"query": VIEWER, "operationName": "Viewer", "variables": {}}


def test_unsupported_is_remembered_per_client(mock):
    mock.respond(NOT_SUPPORTED, DATA, DATA)
    Hub(transport=mock).viewer()
    Hub(transport=mock).viewer()
    assert ["query" in body for body in bodies(mock)] == [False, True, False]


def test_async_miss(hub, mock):
    mock.respond(NOT_FOUND, DATA)
    assert asyncio.run(hub.aio.viewer()) == "octo"
    assert ["query" in body for body in bodies(mock)] == [False, True]


def test_async_unsupported(hub, mock):
    mock.respond(NOT_SUPPORTED, DATA, DATA)

    async def twice():
        return [await hub.aio.viewer(), await hub.aio.viewer()]

    assert asyncio.run(twice()) == ["octo", "octo"]
    assert ["extensions" in body for body in bodies(mock)] == [True, False, False]


def test_variables_and_signatures_are_unchanged(mock):
    class Api(Client):
        base_url = "https://x.test"

        @graphql_route(
            "query R($owner: String!) { repository(owner: $owner) { id } }", persisted=True
        )
        def repo(self, owner: str) -> dict: ...

    import inspect

    api = Api(transport=mock)
    assert list(inspect.signature(api.repo).parameters) == ["owner"]
    mock.respond(NOT_FOUND, graphql_response(data={"repository": None}))
    assert api.repo("acme") == {"repository": None}
    assert [body["variables"] for body in bodies(mock)] == [{"owner": "acme"}] * 2


def test_paginated_and_persisted(mock):
    document = """
    query Issues($after: String) {
      viewer { issues(first: 1, after: $after) { pageInfo { hasNextPage endCursor } nodes { n } } }
    }
    """

    class Api(Client):
        base_url = "https://x.test"
        issues = graphql_route(document, persisted=True, paginate="viewer.issues")

    def page(n, cursor=None, more=False):
        connection = {"pageInfo": {"hasNextPage": more, "endCursor": cursor}, "nodes": [{"n": n}]}
        return graphql_response(data={"viewer": {"issues": connection}})

    mock.respond(page(1, "c1", True), NOT_FOUND, page(2))
    assert [item["n"] for item in Api(transport=mock).issues()] == [1, 2]
    first, second, third = bodies(mock)
    assert "query" not in first and "query" not in second and "query" in third
    assert second["variables"] == third["variables"] == {"after": "c1"}


def test_hooks_see_each_request(mock):
    seen = []

    class Api(Hub):
        def on_request(self, request):
            seen.append((request.operation, b'"query"' in request.content))

    mock.respond(NOT_FOUND, DATA)
    Api(transport=mock).viewer()
    assert seen == [("Viewer", False), ("Viewer", True)]
