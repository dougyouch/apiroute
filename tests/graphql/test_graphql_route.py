import asyncio
import inspect
import subprocess
import sys
from dataclasses import dataclass

import httpx
import pytest

from apiroute import (
    Client,
    GraphQLError,
    Header,
    Result,
    Retries,
    RouteDefinitionError,
    Section,
    UnexpectedResponse,
    graphql_route,
    namespace,
)
from apiroute.testing import MockTransport, UnmatchedRequest, graphql_response

REPO = """
query Repo($owner: String!, $repoName: String!, $first: Int) {
  repository(owner: $owner, name: $repoName) { name issues(first: $first) { totalCount } }
}
"""
STAR = "mutation Star($id: ID!) { addStar(input: {starrableId: $id}) { clientMutationId } }"


@dataclass
class Viewer:
    login: str


class GitHub(Client):
    base_url = "https://api.github.test"
    headers = {"Authorization": "Bearer t"}
    retries = Retries(attempts=3, sleep=0)
    org = "acme"

    @graphql_route(REPO, data="repository")
    def repo(self, owner: str, repo_name: str, first: int | None = None) -> dict: ...

    viewer = graphql_route("query Viewer { viewer { login } }", data="viewer", model=Viewer)

    org_repos = graphql_route(
        "query OrgRepos($org: String!, $first: Int!) { organization(login: $org) { name } }"
    )

    @graphql_route(STAR)
    def star(self, id: str) -> dict: ...

    @graphql_route(STAR, idempotent=True, operation_name="Star")
    def star_again(self, id: str) -> dict: ...

    class admin(Section):
        with namespace("/v4"):
            ping = graphql_route("{ ping }")


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def github(mock):
    return GitHub(transport=mock, async_transport=mock.aio)


def test_a_def_sends_the_operation_and_returns_data(github, mock):
    mock.respond(graphql_response(data={"repository": {"name": "x"}}))
    assert github.repo("acme", "x", first=5) == {"name": "x"}
    call = mock.last
    assert call.method == "POST"
    assert str(call.url) == "https://api.github.test/graphql"
    assert call.json() == {
        "query": REPO,
        "operationName": "Repo",
        "variables": {"owner": "acme", "repoName": "x", "first": 5},
    }
    assert call.headers["Content-Type"] == "application/json"
    assert call.headers["Accept"] == "application/graphql-response+json, application/json"
    assert call.headers["Authorization"] == "Bearer t"


def test_none_arguments_are_left_out(github, mock):
    mock.respond(graphql_response(data={"repository": None}))
    assert github.repo("acme", "x") is None
    assert mock.last.graphql_variables == {"owner": "acme", "repoName": "x"}


def test_a_bare_assignment_converts_to_the_model(github, mock):
    mock.respond(graphql_response(data={"viewer": {"login": "octocat"}}))
    assert github.viewer() == Viewer("octocat")
    assert mock.last.json()["variables"] == {}


def test_a_generated_signature_takes_the_variables_in_snake_case():
    class Api(Client):
        repo = graphql_route(REPO)

    assert str(inspect.signature(Api(base_url="https://x.test").repo)) == (
        "(*, owner, repo_name, first=None)"
    )


def test_a_client_attribute_fills_a_variable(github, mock):
    assert str(inspect.signature(github.org_repos)) == "(*, org=FROM_CLIENT, first)"
    mock.respond(graphql_response(data={"organization": None}))
    github.org_repos(first=2)
    assert mock.last.graphql_variables == {"org": "acme", "first": 2}


def test_a_section_and_namespace_prefix_the_path(github, mock):
    mock.respond(graphql_response(data={"ping": "pong"}))
    assert github.admin.ping() == {"ping": "pong"}
    assert mock.last.path == "/v4/graphql"
    assert "operationName" not in mock.last.json()
    assert mock.last.operation == "ping"  # an anonymous operation is named by its method


def test_async_calls_send_the_same_request(github, mock):
    mock.respond(graphql_response(data={"repository": {"name": "x"}}))
    assert asyncio.run(github.aio.repo("acme", "x")) == {"name": "x"}
    assert mock.last.json()["operationName"] == "Repo"


def test_explicit_variable_mapping(mock):
    class Api(Client):
        base_url = "https://x.test"

        @graphql_route(
            "query U($userID: ID!) { node(id: $userID) { id } }", variables={"userID": "uid"}
        )
        def user(self, uid: str): ...

    mock.respond(graphql_response(data={}))
    Api(transport=mock).user("u1")
    assert mock.last.graphql_variables == {"userID": "u1"}


def test_headers_and_result_parameters_are_allowed(mock):
    class Api(Client):
        base_url = "https://x.test"

        @graphql_route("query Viewer { viewer { login } }", data="viewer.login")
        def login(self, trace_id: Header, *, login: Result) -> str:
            return login.upper()

    mock.respond(graphql_response(data={"viewer": {"login": "a"}}))
    assert Api(transport=mock).login("t1") == "A"
    assert mock.last.headers["Trace-Id"] == "t1"
    assert mock.last.graphql_variables == {}


def test_route_headers_are_sent(mock):
    class Api(Client):
        base_url = "https://x.test"
        viewer = graphql_route("{ viewer { id } }", headers={"X-Github-Next-Global-ID": "1"})

    mock.respond(graphql_response(data={}))
    Api(transport=mock).viewer()
    assert mock.last.headers["X-Github-Next-Global-ID"] == "1"


def test_hooks_see_the_operation_name(mock):
    seen = []

    class Api(GitHub):
        def on_request(self, request):
            seen.append(request.operation)

    mock.respond(graphql_response(data={"viewer": {"login": "a"}}))
    Api(transport=mock).viewer()
    assert seen == ["Viewer"]


def test_operation_name_picks_one_of_several(mock):
    class Api(Client):
        base_url = "https://x.test"
        b = graphql_route("query A { a } query B { b }", operation_name="B")

    mock.respond(graphql_response(data={"b": 1}))
    Api(transport=mock).b()
    assert mock.last.json()["operationName"] == "B"


@pytest.mark.parametrize(
    "declare, message",
    [
        (lambda: graphql_route("query A { a } query B { b }"), "several operations"),
        (lambda: graphql_route("subscription S { a }"), "subscriptions"),
        (lambda: graphql_route("{ a }", errors="ignore"), "errors must be one of"),
        (lambda: graphql_route("{ a }", variables={"x": "y"}), r"maps \$x"),
    ],
)
def test_bad_declarations_fail_when_the_class_is_created(declare, message):
    with pytest.raises(RouteDefinitionError, match=rf"Api\.op: .*{message}"):

        class Api(Client):
            op = declare()


def test_a_missing_required_variable_names_the_route():
    with pytest.raises(RouteDefinitionError, match=r"Api\.repo: no argument .* \$owner"):

        class Api(Client):
            @graphql_route(REPO)
            def repo(self, repo_name: str): ...


def test_an_unused_argument_is_an_error():
    with pytest.raises(RouteDefinitionError, match=r"Api\.viewer: parameter 'extra'"):

        class Api(Client):
            @graphql_route("query Viewer { viewer { id } }")
            def viewer(self, extra: str): ...


def test_explicit_mapping_to_a_missing_parameter_is_an_error():
    with pytest.raises(RouteDefinitionError, match=r"fills \$userID from 'uid'"):

        class Api(Client):
            @graphql_route("query U($userID: ID!) { a }", variables={"userID": "uid"})
            def user(self, user_id: str): ...


def test_a_syntax_error_fails_when_the_class_is_created():
    with pytest.raises(RouteDefinitionError, match=r"Api\.viewer: GraphQL syntax error"):

        class Api(Client):
            @graphql_route("query Viewer { viewer(id: ) { login } }")
            def viewer(self): ...


def test_lazy_classes_check_on_first_use(mock):
    class Api(Client):
        base_url = "https://x.test"
        compile_routes = "lazy"

        @graphql_route("query Viewer { viewer(id: ) }")
        def viewer(self): ...

    with pytest.raises(RouteDefinitionError, match="GraphQL syntax error"):
        Api(transport=mock).viewer()


def test_graphql_errors_raise(github, mock):
    mock.respond(graphql_response(data={"viewer": None}, errors=[{"message": "Not allowed"}]))
    with pytest.raises(GraphQLError, match="^Viewer: Not allowed$") as caught:
        github.viewer()
    assert caught.value.data == {"viewer": None}


def test_partial_data_can_be_accepted(mock):
    class Api(Client):
        base_url = "https://x.test"
        both = graphql_route("query Both { a b }", errors="partial")

    mock.respond(graphql_response(data={"a": 1, "b": None}, errors=[{"message": "b failed"}]))
    assert Api(transport=mock).both() == {"a": 1, "b": None}


def test_a_server_error_is_unexpected(github, mock):
    mock.respond(httpx.Response(502, text="bad gateway"))
    with pytest.raises(UnexpectedResponse, match="unexpected status 502"):
        github.viewer()


def test_a_mutation_isnt_retried_after_a_read_timeout(github, mock):
    mock.respond(httpx.ReadTimeout("slow"), graphql_response(data={}))
    with pytest.raises(httpx.ReadTimeout):
        github.star("s1")
    assert len(mock.calls) == 1


def test_a_mutation_is_retried_after_a_connect_error(github, mock):
    mock.respond(httpx.ConnectError("refused"), graphql_response(data={"addStar": {}}))
    assert github.star("s1") == {"addStar": {}}
    assert len(mock.calls) == 2


def test_a_query_is_retried_after_a_read_timeout(github, mock):
    mock.respond(httpx.ReadTimeout("slow"), graphql_response(data={"viewer": {"login": "a"}}))
    assert github.viewer() == Viewer("a")
    assert len(mock.calls) == 2


def test_an_idempotent_mutation_is_retried_after_a_read_timeout(github, mock):
    mock.respond(httpx.ReadTimeout("slow"), graphql_response(data={}))
    assert github.star_again("s1") == {}
    assert len(mock.calls) == 2


def test_async_mutations_arent_retried_after_a_read_timeout(github, mock):
    mock.respond(httpx.ReadTimeout("slow"), graphql_response(data={}))
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(github.aio.star("s1"))
    assert len(mock.calls) == 1


def test_mocks_match_operations_by_name(github, mock):
    mock.on(operation="Viewer").respond(graphql_response(data={"viewer": {"login": "v"}}))
    mock.on(operation="Repo").respond(graphql_response(data={"repository": {"name": "r"}}))
    assert github.repo("acme", "r") == {"name": "r"}
    assert github.viewer() == Viewer("v")


def test_an_unmatched_operation_is_named(github, mock):
    with pytest.raises(UnmatchedRequest, match="Star: POST"):
        github.star("s1")


def test_importing_apiroute_doesnt_import_graphql_core():
    code = "import sys, apiroute; assert 'graphql' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
