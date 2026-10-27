from apiroute.codegen.graphql.operation_collector import OperationCollector
from apiroute.codegen.graphql.operation_documents import OperationDocuments
from tests.codegen.graphql.helpers import SCHEMA, write_operations

CONNECTION = "pageInfo { hasNextPage endCursor } nodes { name }"


def paginated(selection, variables="($after: String)", field="repositories(after: $after)"):
    """An operation paginating the viewer's repositories with this selection."""
    return f"query A{variables} {{ viewer {{ {field} @paginate {{ {selection} }} }} }}"


def collect(tmp_path, files):
    return OperationCollector(write_operations(tmp_path / "ops", files)).collect()


def relative(problems):
    return [str(p).split("/ops/", 1)[1] for p in problems]


def test_the_directive_is_stripped_and_its_path_recorded(tmp_path):
    collected = collect(
        tmp_path,
        {
            "a.graphql": "query A($after: String) { viewer { ... on User { mine: "
            f"repositories(after: $after) @paginate @include(if: true) {{ {CONNECTION} }} }} }} }}"
        },
    )
    operation = collected.operations[0]
    assert operation.paginate.path == "viewer.mine"
    assert operation.paginate.field.loc is not None  # the parsed node, for locations
    docs = OperationDocuments(SCHEMA, collected)
    text = docs.text(operation)
    assert "@paginate" not in text
    assert "@include(if: true)" in text
    assert docs.problems() == []


def test_an_operation_without_it_is_unchanged(tmp_path):
    collected = collect(tmp_path, {"a.graphql": "query A { viewer { login } }"})
    assert collected.operations[0].paginate is None


def test_more_than_one_and_in_fragments_are_problems(tmp_path):
    collected = collect(
        tmp_path,
        {
            "a.graphql": "query A($after: String) {\n  viewer {\n"
            f"    a: repositories(after: $after) @paginate {{ {CONNECTION} }}\n"
            f"    b: repositories(after: $after) @paginate {{ {CONNECTION} }}\n  }}\n}}",
            "f.graphql": f"fragment F on User {{\n  repositories @paginate {{ {CONNECTION} }}\n}}",
        },
    )
    assert relative(collected.problems) == [
        "a.graphql:4:5: an operation paginates one connection; @paginate is also at line 3",
        "f.graphql:2:3: @paginate belongs on a field of the operation, not in a fragment",
    ]


def check(tmp_path, text):
    collected = collect(tmp_path, {"a.graphql": text})
    return relative(OperationDocuments(SCHEMA, collected).problems())


def test_a_connection_with_everything_passes(tmp_path):
    edges = "pageInfo { hasNextPage endCursor } edges { node { name } }"
    assert check(tmp_path, paginated(CONNECTION)) == []
    assert check(tmp_path, paginated(edges)) == []


def test_fragments_count_toward_the_shape(tmp_path):
    collected = collect(
        tmp_path,
        {
            "a.graphql": paginated("...C"),
            "f.graphql": f"fragment C on RepositoryConnection {{ {CONNECTION} }}",
        },
    )
    assert OperationDocuments(SCHEMA, collected).problems() == []


def test_what_a_paginated_connection_must_have(tmp_path):
    problems = check(
        tmp_path,
        "query A {\n  viewer {\n    repositories @paginate "
        "{ pageInfo { hasNextPage last: endCursor } totalCount }\n  }\n}",
    )
    assert problems == [
        "a.graphql:3:5: @paginate needs the operation to declare $after: String",
        "a.graphql:3:5: @paginate needs repositories to select pageInfo { hasNextPage endCursor }",
        "a.graphql:3:5: @paginate needs repositories to select nodes or edges { node }",
    ]


def test_edges_must_select_node(tmp_path):
    problems = check(
        tmp_path,
        "query A($after: String) { viewer { repositories(after: $after) @paginate "
        "{ pageInfo { hasNextPage endCursor } edges { cursor } } } }",
    )
    assert problems == [
        "a.graphql:1:36: @paginate needs repositories to select nodes or edges { node }"
    ]
