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


class KeyedApi(Client):
    base_url = "https://api.keyed.test"
    query_params = {"api_key": "s3cret"}
    retries = Retries(attempts=2, sleep=0)

    def should_retry(self, error, attempt):
        return isinstance(error, UnexpectedResponse) and error.status_code == 429

    @route("/things/{id}")
    def get_thing(self, id: int) -> dict: ...


def test_errors_show_the_url_with_secret_query_values_masked(transport, recorder):
    recorder.respond(httpx.Response(404))
    with pytest.raises(UnexpectedResponse) as raised:
        KeyedApi(transport=transport).get_thing(7)
    message = str(raised.value)
    assert "s3cret" not in message
    assert "GET https://api.keyed.test/things/7?api_key=***" in message
    assert "api_key=s3cret" in str(raised.value.request.url)  # the request itself is untouched


def test_retry_log_lines_show_the_masked_url(transport, recorder, caplog):
    recorder.respond(httpx.Response(429), httpx.Response(429))
    with pytest.raises(UnexpectedResponse):
        KeyedApi(transport=transport).get_thing(7)
    assert "retrying" in caplog.text and "api_key=***" in caplog.text
    assert "s3cret" not in caplog.text


def test_redact_url_can_be_overridden_for_a_key_in_the_path(transport, recorder):
    class PathKeyed(Client):
        base_url = "https://rpc.provider.test/v2/k3y"

        def redact_url(self, url):
            return super().redact_url(url).replace("/v2/k3y", "/v2/***")

        @route("POST", "/")
        def call(self, body: dict) -> dict: ...

    recorder.respond(httpx.Response(500))
    with pytest.raises(UnexpectedResponse) as raised:
        PathKeyed(transport=transport).call({"method": "x"})
    assert "k3y" not in str(raised.value) and "/v2/***" in str(raised.value)


class QueryKeyedApi(Client):
    """A provider whose endpoint carries its key in the query, e.g. https://rpc.test/?api-key=..."""

    query_params = {"cluster": "main"}

    @route("POST", "")
    def call(self, body: dict) -> dict: ...

    @route("/v1/things", query={"page": "{page}"})
    def things(self, page: int) -> dict: ...


def test_a_query_string_in_base_url_reaches_the_wire_and_comes_first(transport, recorder):
    api = QueryKeyedApi(base_url="https://rpc.test/?api-key=k3y&flag", transport=transport)
    api.call({"method": "x"})
    assert str(recorder.last.url) == "https://rpc.test?api-key=k3y&flag=&cluster=main"
    api.things(page=2)
    assert recorder.last.url.path == "/v1/things"
    assert list(recorder.last.url.params.multi_items()) == [
        ("api-key", "k3y"),
        ("flag", ""),
        ("cluster", "main"),
        ("page", "2"),
    ]


def test_an_error_masks_a_key_from_base_urls_query(transport, recorder):
    recorder.respond(httpx.Response(500))
    with pytest.raises(UnexpectedResponse) as raised:
        QueryKeyedApi(base_url="https://rpc.test/?api-key=k3y", transport=transport).call({})
    assert "k3y" not in str(raised.value) and "api-key=***" in str(raised.value)
