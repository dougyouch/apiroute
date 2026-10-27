import json

import graphql
import httpx
import pytest

from apiroute.codegen.graphql.schema_fetcher import SchemaFetcher
from tests.codegen.graphql.helpers import SCHEMA


def fetcher(handler):
    return SchemaFetcher(httpx.Client(transport=httpx.MockTransport(handler)))


def introspection():
    return graphql.graphql_sync(SCHEMA, graphql.get_introspection_query()).data


def test_posts_the_introspection_query_with_the_headers():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": introspection()})

    data = fetcher(handler).introspect("https://x.test/graphql", {"Authorization": "Bearer t"})
    assert "__schema" in data
    assert seen[0].method == "POST"
    assert seen[0].headers["Authorization"] == "Bearer t"
    assert "__schema" in json.loads(seen[0].content)["query"]


@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(401, json={}), "answered HTTP 401"),
        (httpx.Response(200, text="<html>"), "didn't answer with JSON"),
        (httpx.Response(200, json={"errors": [{"message": "no"}]}), "failed: no"),
        (httpx.Response(200, json={"data": None}), "answered without data"),
    ],
)
def test_refusals(response, message):
    with pytest.raises(ValueError, match=message):
        fetcher(lambda request: response).introspect("https://x.test/graphql", {})
