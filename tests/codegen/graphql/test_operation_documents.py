from apiroute.codegen.graphql.operation_collector import OperationCollector
from apiroute.codegen.graphql.operation_documents import OperationDocuments
from tests.codegen.graphql.helpers import SCHEMA, write_operations


def documents(tmp_path, files):
    collected = OperationCollector(write_operations(tmp_path / "ops", files)).collect()
    return collected, OperationDocuments(SCHEMA, collected)


def relative(problems):
    return [str(p).split("/ops/", 1)[1] for p in problems]


def test_valid_operations_have_no_problems(tmp_path):
    _, docs = documents(tmp_path, {"a.graphql": "query A { viewer { login } }"})
    assert docs.problems() == []


def test_problems_from_every_file_with_their_locations(tmp_path):
    _, docs = documents(
        tmp_path,
        {
            "a.graphql": "query A {\n  viewer { logn }\n}",
            "b/b.graphql": 'query B($o: Int!) { repository(owner: $o, name: "x") { name } }',
        },
    )
    problems = relative(docs.problems())
    assert len(problems) == 2
    # file and line; graphql-core versions may point at different nodes on the line
    assert problems[0].startswith("a.graphql:2:")
    assert "Cannot query field 'logn' on type 'User'." in problems[0]
    assert problems[1].startswith("b/b.graphql:1:")
    assert "Variable '$o' of type 'Int!'" in problems[1]


def test_a_broken_fragment_is_reported_once_at_its_own_file(tmp_path):
    _, docs = documents(
        tmp_path,
        {
            "f.graphql": "fragment F on User { nope }",
            "a.graphql": "query A { viewer { ...F } }",
            "b.graphql": "query B { viewer { ...F } }",
        },
    )
    problems = relative(docs.problems())
    assert len(problems) == 1
    assert problems[0].startswith("f.graphql:1:")
    assert "Cannot query field 'nope'" in problems[0]


def test_an_unknown_fragment(tmp_path):
    _, docs = documents(tmp_path, {"a.graphql": "query A { viewer { ...Missing } }"})
    (problem,) = relative(docs.problems())
    assert problem.startswith("a.graphql:1:")
    assert problem.endswith("Unknown fragment 'Missing'.")


def test_deprecated_fields_and_unused_fragments_are_warnings(tmp_path):
    _, docs = documents(
        tmp_path,
        {
            "a.graphql": "query A {\n  viewer { oldLogin }\n}",
            "f.graphql": "fragment Unused on User { id }",
        },
    )
    assert docs.problems() == []
    warnings = relative(docs.warnings())
    assert len(warnings) == 2
    assert warnings[0].startswith("a.graphql:2:")
    assert "User.oldLogin is deprecated. Use login." in warnings[0]
    assert warnings[1] == "f.graphql:1:1: fragment Unused is never used"


def test_the_document_holds_the_operation_and_its_fragments_by_name(tmp_path):
    collected, docs = documents(
        tmp_path,
        {
            "a.graphql": "# comment\nquery A { viewer { ...Z  ...Y } }",
            "f.graphql": "fragment Z on User { id ...X }\nfragment Y on User { login }\n"
            "fragment X on User { name }\nfragment Unused on User { id }",
        },
    )
    assert docs.fragments_used(collected.operations[0].node) == {"X", "Y", "Z"}
    assert docs.text(collected.operations[0]) == (
        "query A {\n  viewer {\n    ...Z\n    ...Y\n  }\n}\n\n"
        "fragment X on User {\n  name\n}\n\n"
        "fragment Y on User {\n  login\n}\n\n"
        "fragment Z on User {\n  id\n  ...X\n}"
    )


def test_typename_is_added_where_type_conditions_need_it(tmp_path):
    collected, docs = documents(
        tmp_path,
        {
            "a.graphql": 'query A { search(query: "q", type: USER) { ... on User { login } } '
            "node(id: 1) { id } "
            'repository(owner: "o", name: "n") { owner { ...O } } }',
            "f.graphql": "fragment O on RepositoryOwner { login ... on User { name } }",
        },
    )
    text = docs.text(collected.operations[0])
    assert 'search(query: "q", type: USER) {\n    __typename\n    ... on User' in text
    assert "node(id: 1) {\n    id\n  }" in text  # no type conditions: left alone
    assert "fragment O on RepositoryOwner {\n  __typename\n  login" in text


def test_an_existing_typename_isnt_repeated(tmp_path):
    collected, docs = documents(
        tmp_path,
        {
            "a.graphql": 'query A { search(query: "q", type: USER) '
            "{ __typename ... on User { id } } }"
        },
    )
    assert docs.text(collected.operations[0]).count("__typename") == 1
