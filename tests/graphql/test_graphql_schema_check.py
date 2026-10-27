import graphql
import pytest

from apiroute.graphql.graphql_schema_check import check_against_schema

SCHEMA = graphql.build_schema(
    "type Query { viewer: User repository(owner: String!, name: String!): Repo }"
    " type User { login: String } type Repo { name: String }"
)


def test_a_valid_document_passes():
    check_against_schema(
        "query R($o: String!, $n: String!) { repository(owner: $o, name: $n) { name } }", SCHEMA
    )


def test_lists_every_problem_with_its_location():
    with pytest.raises(ValueError) as caught:
        check_against_schema(
            'query V {\n  viewer { logn }\n  repository(owner: "a") { name }\n}', SCHEMA
        )
    header, *problems = str(caught.value).split("\n  - ")
    assert header == "the document doesn't match graphql_schema:"
    # graphql-core's wording varies between versions; the locations don't
    assert len(problems) == 2
    assert problems[0].startswith("Cannot query field 'logn' on type 'User'.")
    assert problems[0].endswith("(line 2, column 12)")
    assert "is required, but it was not provided." in problems[1]
    assert problems[1].endswith("(line 3, column 3)")


def test_a_variable_of_the_wrong_type():
    expected = "Variable '\\$o' of type 'Boolean!' used in position expecting type 'String!'"
    with pytest.raises(ValueError, match=expected):
        check_against_schema(
            'query R($o: Boolean!) { repository(owner: $o, name: "n") { name } }', SCHEMA
        )


def test_a_syntax_error():
    with pytest.raises(ValueError, match="GraphQL syntax error"):
        check_against_schema("query { viewer(", SCHEMA)
