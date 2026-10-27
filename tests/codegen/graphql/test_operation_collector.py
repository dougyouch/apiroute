import pytest

from apiroute.codegen.graphql.operation_collector import OperationCollector
from tests.codegen.graphql.helpers import write_operations


def collect(tmp_path, files):
    return OperationCollector(write_operations(tmp_path / "ops", files)).collect()


def test_files_in_path_order_with_sections_and_comments(tmp_path):
    collected = collect(
        tmp_path,
        {
            "viewer.graphql": "# The signed-in user.\n# Two lines.\nquery Viewer { viewer { id } }",
            "repos/deep/repo.gql": "query Repo { viewer { id } }\nfragment F on User { id }",
            "notes.txt": "not an operation file",
        },
    )
    assert [(d.node.name.value, d.section, d.comment) for d in collected.operations] == [
        ("Repo", "repos", ""),
        ("Viewer", "", "The signed-in user.\nTwo lines."),
    ]
    assert list(collected.fragments) == ["F"]
    assert collected.problems == []


def test_a_comment_separated_by_code_isnt_a_docstring(tmp_path):
    collected = collect(tmp_path, {"a.graphql": "# about A\nquery A { a }\nquery B { b }"})
    assert [d.comment for d in collected.operations] == ["about A", ""]


def test_problems_are_collected_with_their_locations(tmp_path):
    collected = collect(
        tmp_path,
        {
            "a.graphql": "query { viewer { id } }\nsubscription S { a }",
            "b.graphql": "query Dup { a }\nfragment F on User { id }",
            "c.graphql": "\n\nquery Dup { b }\nfragment F on User { login }",
            "d.graphql": "query Broken { viewer(",
            "e.graphql": "type Extra { a: Int }",
        },
    )
    messages = [str(p).split("/ops/", 1)[1] for p in collected.problems]
    assert messages == [
        "a.graphql:1:1: operations must be named",
        "a.graphql:2:1: subscriptions aren't supported",
        f"c.graphql:3:1: operation Dup is also defined at {tmp_path}/ops/b.graphql:1:1",
        f"c.graphql:4:1: fragment F is also defined at {tmp_path}/ops/b.graphql:2:1",
        "d.graphql:1:23: Syntax Error: Expected Name, found <EOF>.",
        "e.graphql:1:1: only operations and fragments belong in operation files",
    ]
    assert [d.node.name.value for d in collected.operations] == ["Dup"]


def test_a_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="isn't a directory"):
        OperationCollector(str(tmp_path / "nope")).collect()


def test_a_directory_without_operations(tmp_path):
    (tmp_path / "ops").mkdir()
    with pytest.raises(ValueError, match="no .graphql files"):
        OperationCollector(str(tmp_path / "ops")).collect()
