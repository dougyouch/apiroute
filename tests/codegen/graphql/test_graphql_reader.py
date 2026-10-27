import builtins

import graphql
import httpx
import pytest

from apiroute.codegen.graphql.graphql_reader import GraphQLReader
from apiroute.codegen.graphql.schema_fetcher import SchemaFetcher
from tests.codegen.conftest import GRAPHQL
from tests.codegen.graphql.helpers import SCHEMA, write_operations

SCHEMA_FILE = str(GRAPHQL / "schema.graphql")
OPS = str(GRAPHQL / "ops")


def read(operations=OPS, **options):
    return GraphQLReader(SCHEMA_FILE, operations, "HubApi", **options).read()


def test_operations_grouped_into_root_and_sections():
    definition = read(endpoint="https://api.hub.test/graphql")
    assert definition.base_url == "https://api.hub.test"
    assert definition.source == "schema.graphql and ops"
    assert definition.description == "A small code-hosting API."
    assert [o.name for o in definition.root.operations] == ["search", "viewer"]
    assert [(g.name, g.class_name) for g in definition.groups] == [("repos", "ReposSection")]
    assert [o.name for o in definition.groups[0].operations] == ["repository", "star"]


def test_an_operation():
    search = read().root.operations[0]
    assert (search.method, search.path, search.operation_id) == ("POST", "/graphql", "Search")
    assert search.summary == "Users and repositories matching a query."
    assert (search.response.expr, search.response_plain) == ("SearchResult", "dict[str, Any]")
    assert search.graphql.operation_type == "query"
    assert search.graphql.document.startswith("query Search(")
    assert [(p.name, p.wire_name, p.type.expr, p.required) for p in search.parameters] == [
        ("query", "query", "str", True),
        ("type_", "type", "SearchType", True),
        ("from_", "from", "int", False),
    ]


def test_a_mutation_and_a_variable_with_a_default():
    definition = read()
    star = definition.groups[0].operations[1]
    assert star.graphql.operation_type == "mutation"
    assert star.parameters[0].type.expr == "AddStarInput"
    viewer = definition.root.operations[1]
    assert [(p.name, p.required) for p in viewer.parameters] == [("full", False)]


def test_endpoints():
    assert read().base_url is None
    assert read(endpoint="https://x.test").root.operations[0].path == ""
    assert read(endpoint="https://x.test/v4/graphql/").root.operations[0].path == "/v4/graphql"
    with pytest.raises(ValueError, match="without a query"):
        read(endpoint="https://x.test/graphql?key=1")


def test_models_are_sorted_and_only_reached_ones_exist():
    models = read(scalars={"DateTime": ("datetime", "datetime")}).models
    assert list(models) == sorted(models)
    assert "DateTime" in models and "URI" not in models
    assert "Visibility" in models and "SearchType" in models


def test_every_problem_is_raised_together(tmp_path):
    operations = write_operations(
        tmp_path / "ops",
        {"a.graphql": "query A { viewer { logn } }", "b.graphql": "query { viewer { id } }"},
    )
    with pytest.raises(ValueError) as caught:
        read(operations)
    message = str(caught.value)
    assert message.startswith("the operations don't match the schema:\n  ")
    assert "a.graphql:1:" in message and "Cannot query field 'logn'" in message
    assert "b.graphql:1:1: operations must be named" in message


def test_warnings_dont_stop_reading(tmp_path):
    operations = write_operations(
        tmp_path / "ops", {"a.graphql": "query A { viewer { oldLogin } }"}
    )
    definition = read(operations)
    assert len(definition.warnings) == 1
    assert "User.oldLogin is deprecated" in definition.warnings[0]


def test_a_schema_from_an_endpoint(tmp_path):
    seen = []

    def handler(request):
        seen.append(request.headers.get("Authorization"))
        data = graphql.graphql_sync(SCHEMA, graphql.get_introspection_query()).data
        return httpx.Response(200, json={"data": data})

    fetcher = SchemaFetcher(httpx.Client(transport=httpx.MockTransport(handler)))
    reader = GraphQLReader(
        "https://api.hub.test/graphql",
        OPS,
        "HubApi",
        headers={"Authorization": "t"},
        fetcher=fetcher,
    )
    definition = reader.read()
    assert seen == ["t"]
    assert definition.source == "https://api.hub.test/graphql and ops"


def test_needs_graphql_core(monkeypatch):
    real_import = builtins.__import__

    def without_graphql(name, *args, **kwargs):
        if name == "graphql" or name.startswith("graphql."):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_graphql)
    with pytest.raises(RuntimeError, match=r"pip install apiroute\[codegen\]"):
        read()
