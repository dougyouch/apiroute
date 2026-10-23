import httpx
import pytest

from apiroute import FROM_CLIENT, Client, Query, Section, route


class Api(Client):
    base_url = "https://x.test"
    org: str

    def __init__(self, org="acme", **kwargs):
        super().__init__(**kwargs)
        self.org = org

    get_user = route("/users/:username")
    list_repos = route("/orgs/{org}/repos", query={"page": "{page}"})
    create_thing = route("/things")

    @route("/orgs/{org}/members")
    def list_members(self, org: str = FROM_CLIENT, role: Query = "all"): ...

    class teams(Section):
        org: str

        list = route("/orgs/{org}/teams")


@pytest.fixture
def api(transport):
    return Api(transport=transport)


def test_generated_route_sends_keyword_arguments(api, recorder):
    api.get_user(username="octocat")
    assert str(recorder.last.url) == "https://x.test/users/octocat"


def test_declared_names_fall_back_to_the_instance(api, recorder):
    api.list_repos(page=2)
    assert str(recorder.last.url) == "https://x.test/orgs/acme/repos?page=2"
    api.list_repos(org="other", page=1)
    assert recorder.last.url.path == "/orgs/other/repos"


def test_arguments_are_keyword_only_and_required(api):
    with pytest.raises(TypeError):
        api.get_user("octocat")
    with pytest.raises(TypeError):
        api.list_repos()


def test_generated_body_parameter(api, recorder):
    api.create_thing(body={"a": 1})
    assert recorder.last.method == "POST"
    assert recorder.last_json() == {"a": 1}
    api.create_thing()
    assert recorder.last.content == b""


def test_from_client_works_on_a_def_too(api, recorder):
    api.list_members()
    assert str(recorder.last.url) == "https://x.test/orgs/acme/members?role=all"
    api.list_members(org="other")
    assert recorder.last.url.path == "/orgs/other/members"


def test_section_routes_fall_back_to_the_root_client(transport, recorder):
    Api(org="root-org", transport=transport).teams.list()
    assert recorder.last.url.path == "/orgs/root-org/teams"


def test_routes_can_be_called_through_the_class(api, recorder):
    recorder.respond(httpx.Response(200, json={"login": "a"}))
    assert Api.get_user(api, username="a") == {"login": "a"}


def test_with_options_applies_to_generated_routes(api, recorder):
    api.with_options(query={"x": "1"}).get_user(username="a")
    assert recorder.last.url.params["x"] == "1"
