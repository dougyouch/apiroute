import builtins
import json
from pathlib import Path

import graphql
import pytest

from apiroute.graphql import graphql_schema_loader
from apiroute.graphql.graphql_schema_loader import load_schema

SCHEMAS = Path(__file__).parent / "schemas"


def holder(source):
    return type("Holder", (), {"graphql_schema": source, "__module__": __name__})


def test_sdl_relative_to_the_declaring_module():
    schema = load_schema(holder("schemas/github.graphql"))
    assert "login" in schema.type_map["User"].fields


def test_introspection_with_and_without_the_data_envelope(tmp_path):
    assert "Repository" in load_schema(holder("schemas/github.json")).type_map
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps(json.loads((SCHEMAS / "github.json").read_text())["data"]))
    assert "Repository" in load_schema(holder(bare)).type_map


def test_directive_locations_unknown_to_graphql_core_are_dropped(tmp_path):
    data = json.loads((SCHEMAS / "github.json").read_text())
    for directive in data["data"]["__schema"]["directives"]:
        directive["locations"].append("FROM_A_FUTURE_SPEC")
    future = tmp_path / "future.json"
    future.write_text(json.dumps(data))
    schema = load_schema(holder(future))
    assert "FROM_A_FUTURE_SPEC" not in str(schema.get_directive("deprecated").locations)


def test_a_schema_object_is_used_as_is():
    schema = graphql.build_schema("type Query { a: Int }")
    assert load_schema(holder(schema)) is schema


def test_a_subclass_resolves_against_the_declaring_class():
    base = holder("schemas/github.graphql")
    sub = type("Sub", (base,), {"__module__": "somewhere.else"})
    assert "User" in load_schema(sub).type_map


def test_a_missing_file_names_the_absolute_path():
    with pytest.raises(
        ValueError, match=r"can't read GraphQL schema /.*/tests/graphql/nope\.graphql"
    ):
        load_schema(holder("nope.graphql"))


def test_invalid_sdl(tmp_path):
    bad = tmp_path / "bad.graphql"
    bad.write_text("type Query {")
    with pytest.raises(ValueError, match=r"bad\.graphql isn't a valid schema"):
        load_schema(holder(bad))


def test_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    with pytest.raises(ValueError, match=r"bad\.json isn't a valid schema"):
        load_schema(holder(bad))


def test_rejects_other_values():
    with pytest.raises(TypeError, match="must be a file path or a graphql.GraphQLSchema"):
        load_schema(holder(42))


def test_each_file_is_built_once(tmp_path, monkeypatch):
    path = tmp_path / "once.graphql"
    path.write_text("type Query { a: Int }")
    built = []
    real = graphql.build_schema
    monkeypatch.setattr(
        graphql, "build_schema", lambda text, **kw: built.append(text) or real(text, **kw)
    )
    first = load_schema(holder(path))
    assert load_schema(holder(str(path))) is first
    assert len(built) == 1


def test_needs_graphql_core(monkeypatch):
    real_import = builtins.__import__

    def without_graphql(name, *args, **kwargs):
        if name == "graphql" or name.startswith("graphql."):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_graphql)
    with pytest.raises(ValueError, match=r"pip install apiroute\[graphql\]"):
        load_schema(holder("schemas/github.graphql"))


@pytest.fixture(autouse=True)
def _fresh_cache():
    graphql_schema_loader.load_schema_file.cache_clear()
    yield
    graphql_schema_loader.load_schema_file.cache_clear()


# GitHub's published schema deprecates fields its interfaces don't, which graphql-core 3.3
# rejects as an invalid schema; schemas describe what a server answers, so they're trusted
LENIENT_SDL = """
interface Node { id: ID! }
type Repo implements Node { id: ID! @deprecated(reason: "Use nodeId.") name: String }
type Query { node: Node repo: Repo }
"""


def test_schemas_that_break_newer_graphql_core_rules_still_load(tmp_path):
    from apiroute.graphql.graphql_schema_check import check_against_schema

    path = tmp_path / "lenient.graphql"
    path.write_text(LENIENT_SDL)
    schema = load_schema(holder(path))
    check_against_schema("query R { repo { id name } }", schema)
    with pytest.raises(ValueError, match="Cannot query field 'nope'"):
        check_against_schema("query R { repo { nope } }", schema)
    data = graphql.graphql_sync(schema, graphql.get_introspection_query()).data
    introspected = tmp_path / "lenient.json"
    introspected.write_text(json.dumps({"data": data}))
    check_against_schema("query R { repo { id } }", load_schema(holder(introspected)))
