import httpx
import pytest

from apiroute import Client, Retries, UnexpectedResponse, route
from apiroute.testing import MockTransport, UnmatchedRequest


class Api(Client):
    base_url = "https://x.test/v1?key=k"
    retries = Retries(attempts=3, sleep=0)

    @route("/users/{username}", operation="getUser")
    def get_user(self, username: str): ...

    @route("POST", "/things", body={"name": "{name}"}, query={"draft": "{draft}"})
    def create_thing(self, name: str, draft: bool = False): ...

    @route("/events", stream="iter")
    def get_events(self): ...


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def api(mock):
    return Api(transport=mock)


def test_a_queued_response_answers_and_the_call_is_recorded(api, mock):
    mock.respond(httpx.Response(200, json={"login": "octocat"}))
    assert api.get_user("octocat") == {"login": "octocat"}
    assert mock.last.operation == "getUser"
    assert mock.last.method == "GET"
    assert mock.last.path == "/v1/users/octocat"
    assert mock.last.params["key"] == "k"


def test_the_request_is_encoded_as_on_the_wire(api, mock):
    mock.respond(httpx.Response(201, json={}))
    api.create_thing("a", draft=True)
    assert mock.last.json() == {"name": "a"}
    assert mock.last.params["draft"] == "true"
    assert mock.last.headers["Content-Type"] == "application/json"


def test_queued_responses_answer_in_order(api, mock):
    mock.respond(httpx.Response(200, json=1), httpx.Response(200, json=2))
    assert [api.get_user("a"), api.get_user("b")] == [1, 2]
    assert mock.pending == []


def test_routes_match_before_the_queue_and_their_last_response_repeats(api, mock):
    users = mock.on(operation="getUser").respond(httpx.Response(200, json="user"))
    mock.respond(httpx.Response(201, json="created"))
    assert [api.get_user("a"), api.get_user("b"), api.create_thing("x")] == [
        "user",
        "user",
        "created",
    ]
    assert [call.path for call in users.calls] == ["/v1/users/a", "/v1/users/b"]
    assert api.last_response.request.url.path == "/v1/things"


def test_a_repeated_response_gets_its_own_request(api, mock):
    mock.on(operation="getUser").respond(httpx.Response(200, json={}))
    api.get_user("a")
    first = api.last_response
    api.get_user("b")
    assert first.request.url.path == "/v1/users/a"
    assert api.last_response is not first


def test_routes_match_on_method_path_and_a_predicate(api, mock):
    mock.on(
        method="post", path="/v1/things", where=lambda call: call.json()["name"] == "b"
    ).respond(httpx.Response(200, json="b"))
    mock.on(method="POST").respond(httpx.Response(200, json="other"))
    assert api.create_thing("b") == "b"
    assert api.create_thing("c") == "other"


def test_a_route_without_a_response_fails(api, mock):
    mock.on(operation="getUser")
    with pytest.raises(AssertionError, match="getUser.*has no response"):
        api.get_user("a")


def test_an_unmatched_request_fails_naming_the_call(api, mock):
    with pytest.raises(UnmatchedRequest, match=r"getUser: GET https://x.test/v1/users/a") as raised:
        api.get_user("a")
    assert raised.value.call is mock.last


def test_a_handler_answers_what_nothing_else_does(api):
    mock = MockTransport(lambda request: httpx.Response(200, json=request.url.path))
    assert Api(transport=mock).get_user("a") == "/v1/users/a"


def test_a_callable_response_gets_the_request(api, mock):
    mock.respond(lambda request: httpx.Response(200, json=request.method))
    assert api.get_user("a") == "GET"


def test_a_queued_exception_is_raised_with_its_request_and_retried(api, mock):
    mock.respond(httpx.ConnectError("down"), httpx.Response(200, json="ok"))
    assert api.get_user("a") == "ok"
    assert len(mock.calls) == 2


def test_exceptions_carry_the_request(api, mock):
    error = httpx.ConnectError("down")
    mock.on(operation="getUser").respond(error)
    with pytest.raises(httpx.ConnectError):
        api.get_user("a")
    assert error.request.url.path == "/v1/users/a"


def test_status_errors_are_raised_as_usual(api, mock):
    mock.respond(httpx.Response(404, text="missing"))
    with pytest.raises(UnexpectedResponse) as raised:
        api.get_user("a")
    assert raised.value.status_code == 404


def test_streaming_routes_read_the_mock_body(api, mock):
    mock.respond(httpx.Response(200, content=iter([b"ab", b"cd"])))
    assert b"".join(api.get_events()) == b"abcd"


def test_the_async_side_shares_routes_queue_and_calls(mock):
    assert mock.aio.mock is mock
