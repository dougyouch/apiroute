import httpx
import pytest

from apiroute import Client, Retries, UnexpectedResponse, route


class GitHubApi(Client):
    base_url = "https://api.github.test"
    headers = {"Authorization": lambda self: f"Bearer {self.access_token}"}
    retries = Retries(attempts=3, sleep=0)

    def __init__(self, access_token, org="acme", **kwargs):
        super().__init__(**kwargs)
        self.access_token = access_token
        self.org = org

    @route("/users/{username}")
    def get_user(self, username: str) -> dict:
        """Fetches one user."""

    @route("/orgs/{org}/repos", body={"name": "{name}", "private": "{private}"})
    def create_org_repo(self, name: str, private: bool = False) -> dict: ...

    @route("/status", returns="text")
    def get_status(self) -> str: ...


@pytest.fixture
def client(transport):
    return GitHubApi("secret", transport=transport)


def test_get_returns_parsed_json(client, recorder):
    recorder.respond(httpx.Response(200, json={"login": "octocat"}))
    assert client.get_user("octocat") == {"login": "octocat"}
    assert recorder.last.method == "GET"
    assert str(recorder.last.url) == "https://api.github.test/users/octocat"
    assert recorder.last.headers["Authorization"] == "Bearer secret"
    assert client.last_response.status_code == 200


def test_post_body_uses_arguments_and_attributes(client, recorder):
    client.create_org_repo(name="api", private=True)
    assert recorder.last.method == "POST"
    assert recorder.last.url.path == "/orgs/acme/repos"
    assert recorder.last_json() == {"name": "api", "private": True}


def test_keeps_the_method_signature_and_docstring():
    assert GitHubApi.get_user.__doc__ == "Fetches one user."
    assert GitHubApi.get_user.__wrapped__.__name__ == "get_user"


def test_wrong_arguments_raise_type_error(client):
    with pytest.raises(TypeError):
        client.get_user()


def test_retries_network_errors(client, recorder):
    recorder.respond(httpx.ConnectError("refused"), httpx.Response(200, text="up"))
    assert client.get_status() == "up"
    assert len(recorder.requests) == 2


def test_does_not_retry_unexpected_responses_by_default(client, recorder):
    recorder.respond(httpx.Response(503))
    with pytest.raises(UnexpectedResponse):
        client.get_status()
    assert len(recorder.requests) == 1


def test_should_retry_can_be_overridden(transport, recorder):
    class Patient(GitHubApi):
        def should_retry(self, error, attempt):
            return isinstance(error, UnexpectedResponse) and error.status_code == 503

    recorder.respond(httpx.Response(503), httpx.Response(200, text="up"))
    assert Patient("s", transport=transport).get_status() == "up"


def test_base_url_can_be_overridden_per_instance(transport, recorder):
    GitHubApi("s", base_url="https://ghe.test/api/v3", transport=transport).get_user("a")
    assert str(recorder.last.url) == "https://ghe.test/api/v3/users/a"


def test_rejects_a_bad_instance_base_url():
    with pytest.raises(ValueError, match="scheme"):
        GitHubApi("s", base_url="file:///etc")


def test_escape_path_can_be_overridden(transport, recorder):
    class Nested(GitHubApi):
        def escape_path(self, value):
            return str(value)

    Nested("s", transport=transport).get_user("a/b")
    assert recorder.last.url.path == "/users/a/b"
