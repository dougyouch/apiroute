import builtins

import graphql
import pytest

from apiroute import Client, RouteDefinitionError, Section, graphql_route
from apiroute.graphql import graphql_schema_loader
from apiroute.testing import MockTransport, graphql_response

BAD_FIELD = "query Viewer { viewer { logn } }"
GOOD = "query Viewer { viewer { login } }"


class GitHub(Client):
    base_url = "https://api.github.test"
    graphql_schema = "schemas/github.graphql"


def test_valid_routes_are_created_and_work():
    class Api(GitHub):
        viewer = graphql_route(GOOD, data="viewer.login")

        @graphql_route(
            "query Repo($owner: String!, $repoName: String!) {"
            " repository(owner: $owner, name: $repoName) { stargazerCount } }",
            data="repository.stargazerCount",
        )
        def stars(self, owner: str, repo_name: str) -> int: ...

        star = graphql_route(
            "mutation Star($id: ID!) { addStar(input: {starrableId: $id}) { clientMutationId } }"
        )

    mock = MockTransport()
    mock.respond(graphql_response(data={"repository": {"stargazerCount": 3}}))
    assert Api(transport=mock).stars("a", "b") == 3


def test_an_unknown_field_fails_when_the_class_is_created():
    with pytest.raises(RouteDefinitionError) as caught:

        class Api(GitHub):
            viewer = graphql_route(BAD_FIELD)

    message = str(caught.value)
    assert message.endswith(
        "<locals>.Api.viewer: the document doesn't match graphql_schema:\n  - "
        "Cannot query field 'logn' on type 'User'. Did you mean 'login'? (line 1, column 25)"
    )


def test_a_variable_of_the_wrong_type():
    with pytest.raises(
        RouteDefinitionError, match="'Int!' used in position expecting type 'String!'"
    ):

        class Api(GitHub):
            repo = graphql_route(
                'query Repo($owner: Int!) { repository(owner: $owner, name: "x") { name } }'
            )


def test_every_problem_is_reported():
    with pytest.raises(RouteDefinitionError) as caught:

        class Api(GitHub):
            @graphql_route('query Repo { viewer { logn } repository(owner: "a") { name } }')
            def repo(self): ...

    message = str(caught.value)
    assert "Cannot query field 'logn'" in message
    assert "is required, but it was not provided" in message


def test_introspection_json_and_schema_objects_work_too():
    schema = graphql.build_schema("type Query { ping: String }")

    class FromJson(Client):
        graphql_schema = "schemas/github.json"
        viewer = graphql_route(GOOD)

    class FromObject(Client):
        graphql_schema = schema
        ping = graphql_route("{ ping }")

    with pytest.raises(RouteDefinitionError, match="Cannot query field 'viewer'"):

        class Wrong(Client):
            graphql_schema = schema
            viewer = graphql_route(GOOD)


def test_lazy_classes_validate_on_first_use():
    class Api(GitHub):
        compile_routes = "lazy"
        viewer = graphql_route(BAD_FIELD)

    with pytest.raises(RouteDefinitionError, match="Cannot query field 'logn'"):
        Api(transport=MockTransport()).viewer()


def test_sections_use_the_enclosing_schema():
    with pytest.raises(
        RouteDefinitionError, match=r"Api\.admin\.viewer: the document doesn't match"
    ):

        class Api(GitHub):
            class admin(Section):
                viewer = graphql_route(BAD_FIELD)


def test_nested_sections_use_the_client_schema():
    with pytest.raises(RouteDefinitionError, match=r"Api\.a\.b\.viewer: the document"):

        class Api(GitHub):
            class a(Section):
                class b(Section):
                    viewer = graphql_route(BAD_FIELD)


def test_lazy_sections_validate_on_first_use():
    class Api(GitHub):
        class admin(Section):
            compile_routes = "lazy"
            viewer = graphql_route(BAD_FIELD)

    with pytest.raises(RouteDefinitionError, match="Cannot query field 'logn'"):
        Api(transport=MockTransport()).admin.viewer()


def test_a_section_can_opt_out():
    class Api(GitHub):
        class legacy(Section):
            graphql_schema = None
            viewer = graphql_route(BAD_FIELD)


def test_a_section_schema_wins_over_the_client_schema():
    class Api(GitHub):
        class other(Section):
            graphql_schema = graphql.build_schema("type Query { ping: String }")
            ping = graphql_route("{ ping }")


def test_validate_false_skips_one_route():
    class Api(GitHub):
        preview = graphql_route("query Preview { viewer { sponsorsListing } }", validate=False)
        viewer = graphql_route(GOOD)

    with pytest.raises(RouteDefinitionError, match="GraphQL syntax error"):

        class Broken(GitHub):
            preview = graphql_route("query Preview { viewer( }", validate=False)


def test_without_a_schema_nothing_is_validated():
    class Api(Client):
        viewer = graphql_route(BAD_FIELD)


def test_a_missing_schema_file_names_the_path():
    with pytest.raises(
        RouteDefinitionError, match=r"Api\.viewer: can't read GraphQL schema /\S+/missing\.graphql"
    ):

        class Api(Client):
            graphql_schema = "missing.graphql"
            viewer = graphql_route(GOOD)


def test_a_schema_without_graphql_core_is_an_error(monkeypatch):
    real_import = builtins.__import__

    def without_graphql(name, *args, **kwargs):
        if name == "graphql" or name.startswith("graphql."):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_graphql)
    with pytest.raises(RouteDefinitionError, match=r"pip install apiroute\[graphql\]"):

        class Api(GitHub):
            viewer = graphql_route(GOOD)


def test_two_clients_share_one_loaded_schema(monkeypatch):
    graphql_schema_loader.load_schema_file.cache_clear()
    built = []
    real = graphql.build_schema
    monkeypatch.setattr(
        graphql, "build_schema", lambda text, **kw: built.append(1) or real(text, **kw)
    )

    class One(GitHub):
        viewer = graphql_route(GOOD)

    class Two(GitHub):
        viewer = graphql_route(GOOD)

    assert len(built) == 1
