import pytest

from apiroute.graphql.graphql_variable import GraphQLVariable
from apiroute.graphql.graphql_variable_binder import GraphQLVariableBinder

OWNER = GraphQLVariable("owner", "String!", True, False)
REPO_NAME = GraphQLVariable("repoName", "String!", True, False)
FIRST = GraphQLVariable("first", "Int", False, False)


class Owner:
    org: str
    login = "me"


def binder(*variables, explicit=None):
    return GraphQLVariableBinder(variables, explicit or {}, Owner)


def test_same_name_then_snake_case():
    template = binder(OWNER, REPO_NAME).template(["owner", "repo_name"])
    assert template == {"owner": "{owner}", "repoName": "{repo_name}"}


def test_the_exact_name_wins_over_snake_case():
    assert binder(REPO_NAME).template(["repo_name", "repoName"]) == {"repoName": "{repoName}"}


def test_explicit_mapping_wins():
    template = binder(REPO_NAME, explicit={"repoName": "name"}).template(["name", "repo_name"])
    assert template == {"repoName": "{name}"}


def test_client_attributes_and_annotations_fill_variables():
    org = GraphQLVariable("org", "String!", True, False)
    login = GraphQLVariable("login", "String", False, False)
    assert binder(org, login).template([]) == {"org": "{org}", "login": "{login}"}


def test_an_unfilled_optional_variable_isnt_sent():
    assert binder(FIRST).template([]) == {}


def test_an_unfilled_required_variable_is_an_error():
    with pytest.raises(TypeError, match=r"fills \$repoName; add a 'repo_name' parameter"):
        binder(REPO_NAME).template([])


def test_explicit_mapping_must_name_a_declared_variable():
    with pytest.raises(ValueError, match=r"maps \$nope"):
        binder(OWNER, explicit={"nope": "owner"})


def test_param_names_for_generated_signatures():
    names = binder(REPO_NAME, FIRST, explicit={"first": "limit"})
    assert [names.param_name("repoName"), names.param_name("first")] == ["repo_name", "limit"]
