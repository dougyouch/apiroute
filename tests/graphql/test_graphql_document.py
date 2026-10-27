import pytest

from apiroute.graphql.graphql_document import GraphQLDocument
from apiroute.graphql.graphql_operation import GraphQLOperation
from apiroute.graphql.graphql_variable import GraphQLVariable

REPO = """
query Repo($owner: String!, $name: String!, $first: Int = 10, $after: String) {
  repository(owner: $owner, name: $name) { issues(first: $first, after: $after) { totalCount } }
}
"""


def test_reads_a_named_query_and_its_variables():
    assert GraphQLDocument(REPO).operation() == GraphQLOperation(
        "query",
        "Repo",
        (
            GraphQLVariable("owner", "String!", True, False),
            GraphQLVariable("name", "String!", True, False),
            GraphQLVariable("first", "Int", False, True),
            GraphQLVariable("after", "String", False, False),
        ),
    )


def test_a_non_null_variable_with_a_default_is_optional():
    variable = GraphQLDocument("query A($n: Int! = 5) { a }").operation().variables[0]
    assert variable == GraphQLVariable("n", "Int!", False, True)


def test_list_types_and_object_defaults_and_directives():
    document = GraphQLDocument(
        'query A($ids: [ID!]! @deprecated, $f: Filter = {state: OPEN, labels: ["x"]}) { a }'
    )
    variables = document.operation().variables
    assert [(v.name, v.type, v.required) for v in variables] == [
        ("ids", "[ID!]!", True),
        ("f", "Filter", False),
    ]


def test_mutation():
    operation = GraphQLDocument("mutation Star($id: ID!) { addStar(input: {id: $id}) { ok } }")
    assert operation.operation().type == "mutation"


def test_anonymous_and_shorthand_operations():
    assert GraphQLDocument("query { a }").operation() == GraphQLOperation("query", None, ())
    assert GraphQLDocument("{ a { b } }").operation() == GraphQLOperation("query", None, ())


def test_an_anonymous_operation_keeps_no_name_when_one_is_given():
    assert GraphQLDocument("{ a }").operation("Label").name is None


def test_fragments_are_skipped():
    document = GraphQLDocument(
        "fragment F on User @include(if: true) { login } query Me { viewer { ...F } }"
    )
    assert [operation.name for operation in document.operations] == ["Me"]


def test_several_operations_need_a_name():
    document = GraphQLDocument("query A { a } query B { b }")
    with pytest.raises(ValueError, match="several operations"):
        document.operation()
    assert document.operation("B").name == "B"
    with pytest.raises(ValueError, match="no operation named 'C'"):
        document.operation("C")


def test_comments_and_strings_dont_look_like_variables():
    document = GraphQLDocument('query A($x: Int) # ($fake: Int)\n{ a(s: "$y: String!") { b } }')
    assert [v.name for v in document.operation().variables] == ["x"]


def test_directives_on_the_operation_may_hold_braces():
    document = GraphQLDocument("query A @cached(opts: {ttl: 1}) { a }")
    assert document.operation().name == "A"


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "no operation"),
        ("subscription S { a }", "subscriptions"),
        ("query A { a", "ends early"),
        ("query A { a ) }", "unbalanced"),
        ("query A($x Int) { a }", "expected ':'"),
        ("type User { a }", "expected an operation"),
    ],
)
def test_rejects_documents_it_cant_read(text, message):
    with pytest.raises(ValueError, match=message):
        GraphQLDocument(text)
