import base64
import logging

import httpx
import pytest

from apiroute import Client, Retries, Section, UnexpectedResponse, graphql_route, route
from apiroute.auth import AuthError, OAuth2ClientCredentials
from apiroute.pagination import NextUrl
from apiroute.testing import MockTransport
from apiroute.testing.sleep_recording import recorded_sleeps
from tests.auth.conftest import TOKEN_URL, json_reply


class Api(Client):
    base_url = "https://api.test"

    def __init__(self, client_id="id", client_secret="secret", auth_options=None, **kwargs):
        super().__init__(**kwargs)
        self.authenticator = OAuth2ClientCredentials(
            TOKEN_URL, client_id, client_secret, **(auth_options or {})
        )

    get_order = route("/orders/{id}")
    create_order = route("POST", "/orders")
    feed = route("/stream", stream="sse")
    listing = route("/list", paginate=NextUrl())

    @graphql_route("query Viewer { viewer { login } }")
    def viewer(self): ...

    class reports(Section):
        get_report = route("/reports/{id}")


@pytest.fixture
def api(transport):
    return Api(transport=transport)


def test_fetches_a_token_and_sends_it(api, server):
    assert api.get_order(id=1)["token"] == "token-1"
    assert server.api_tokens == ["Bearer token-1"]


def test_the_token_request_is_a_client_credentials_grant(api, server):
    api.get_order(id=1)
    request = server.token_requests[0]
    assert request.method == "POST"
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Authorization"] == "Basic " + base64.b64encode(b"id:secret").decode()
    assert server.form() == {"grant_type": "client_credentials"}


def test_scope_and_extra_fields_are_sent(transport, server):
    options = {"scope": "orders:read", "extra": {"audience": "https://api.test"}}
    Api(auth_options=options, transport=transport).get_order(id=1)
    assert server.form() == {
        "grant_type": "client_credentials",
        "scope": "orders:read",
        "audience": "https://api.test",
    }


def test_auth_method_post_sends_the_secret_in_the_form(transport, server):
    Api(auth_options={"auth_method": "post"}, transport=transport).get_order(id=1)
    assert "authorization" not in server.token_requests[0].headers
    assert server.form()["client_secret"] == "secret"


def test_the_token_is_reused_until_it_expires(transport, server):
    clock = [0.0]
    api = Api(auth_options={"clock": lambda: clock[0]}, transport=transport)
    api.get_order(id=1)
    api.get_order(id=2)
    assert len(server.token_requests) == 1
    clock[0] = 3600 - 30
    api.get_order(id=3)
    assert len(server.token_requests) == 2
    assert server.api_tokens == ["Bearer token-1", "Bearer token-1", "Bearer token-2"]


def test_a_401_refreshes_the_token_and_sends_once_more(api, server, caplog):
    api.get_order(id=1)
    server.revoke()
    with caplog.at_level(logging.INFO, logger="apiroute"):
        assert api.get_order(id=2)["token"] == "token-2"
    assert server.api_tokens == ["Bearer token-1", "Bearer token-1", "Bearer token-2"]
    assert "credential rejected" in caplog.text


def test_a_post_is_sent_again_after_a_401(api, server):
    api.get_order(id=1)
    server.revoke()
    api.create_order(body={"sku": "a"})
    assert [r.method for r in server.api_requests] == ["GET", "POST", "POST"]
    assert server.api_requests[-1].content == server.api_requests[-2].content


def test_a_second_401_is_raised_without_another_refresh(api, server):
    server.token_replies = [json_reply(200, {"access_token": "bogus"})] * 2
    with pytest.raises(UnexpectedResponse) as raised:
        api.get_order(id=1)
    assert raised.value.status_code == 401
    assert len(server.token_requests) == 2
    assert len(server.api_requests) == 2


def test_the_401_resend_isnt_a_retry(transport, server):
    class Retrying(Api):
        retries = Retries(attempts=2, sleep=0)

        def should_retry(self, error, attempt):
            return isinstance(error, UnexpectedResponse) or super().should_retry(error, attempt)

    server.token_replies = [json_reply(200, {"access_token": "bogus"})] * 4
    with recorded_sleeps(), pytest.raises(UnexpectedResponse):
        Retrying(transport=transport).get_order(id=1)
    # two attempts, each sent with a token and once more with a fresh one; the second attempt
    # starts with the token the first one fetched last
    assert len(server.api_requests) == 4
    assert len(server.token_requests) == 3


def test_other_errors_dont_refresh(server):
    def forbid(request):
        if str(request.url).startswith(TOKEN_URL):
            return server(request)
        return httpx.Response(403)

    with pytest.raises(UnexpectedResponse, match="403"):
        Api(transport=_transport(forbid)).get_order(id=1)
    assert len(server.token_requests) == 1


def test_a_refused_token_request_raises_auth_error(api, server):
    server.token_replies = [
        json_reply(401, {"error": "invalid_client", "error_description": "Bad secret"})
    ]
    with pytest.raises(AuthError) as raised:
        api.get_order(id=1)
    error = raised.value
    assert (error.error, error.description) == ("invalid_client", "Bad secret")
    assert error.response.status_code == 401
    assert str(error) == "token request failed with status 401: invalid_client (Bad secret)"
    assert "secret" not in str(error).lower().replace("bad secret", "")
    assert server.api_requests == []
    assert len(server.token_requests) == 1


def test_a_refusal_without_an_oauth_body_still_raises_auth_error(api, server):
    server.token_replies = [httpx.Response(500, content=b"<html>oops</html>")]
    with pytest.raises(AuthError, match="status 500$") as raised:
        api.get_order(id=1)
    assert raised.value.error is None


def test_a_refusal_with_a_json_list_body(api, server):
    server.token_replies = [json_reply(400, ["nope"])]
    with pytest.raises(AuthError, match="status 400$"):
        api.get_order(id=1)


def test_a_reply_that_isnt_json_raises_auth_error(api, server):
    server.token_replies = [httpx.Response(200, content=b"not json")]
    with pytest.raises(AuthError):
        api.get_order(id=1)


def test_a_reply_without_a_token_raises_auth_error(api, server):
    server.token_replies = [json_reply(200, {"token": "x"})]
    with pytest.raises(AuthError, match="no access_token"):
        api.get_order(id=1)


def test_auth_errors_arent_retried(transport, server):
    class Retrying(Api):
        retries = Retries(attempts=3, sleep=0)

    server.token_replies = [json_reply(400, {"error": "invalid_grant"})] * 3
    with pytest.raises(AuthError):
        Retrying(transport=transport).get_order(id=1)
    assert len(server.token_requests) == 1


def test_a_network_error_reaching_the_token_endpoint_is_retried_by_the_call(transport, server):
    class Retrying(Api):
        retries = Retries(attempts=2, sleep=0)

    server.token_replies = [httpx.ConnectError("refused")]
    with recorded_sleeps():
        assert Retrying(transport=transport).get_order(id=1)["token"] == "token-1"
    assert len(server.token_requests) == 2


def test_sections_use_the_clients_authenticator(api, server):
    assert api.reports.get_report(id=1)["token"] == "token-1"
    api.get_order(id=1)
    assert len(server.token_requests) == 1


def test_on_request_sees_the_authorization_header(transport, server):
    seen = []

    class Signed(Api):
        def on_request(self, request):
            seen.append(request.headers["Authorization"])

    Signed(transport=transport).get_order(id=1)
    assert seen == ["Bearer token-1"]


def test_with_options_headers_dont_override_the_credential(api, server):
    api.with_options(headers={"X-Trace": "1"}).get_order(id=1)
    assert server.api_requests[0].headers["X-Trace"] == "1"
    assert server.api_tokens == ["Bearer token-1"]


def test_streams_refresh_on_401(api, server):
    api.get_order(id=1)
    server.revoke()
    assert [event.data for event in api.feed()] == ["ok"]
    assert server.api_tokens[-1] == "Bearer token-2"


def test_every_page_carries_the_token(transport, server):
    pages = iter(
        [
            httpx.Response(
                200, json=[1], headers={"Link": '<https://api.test/list?p=2>; rel="next"'}
            ),
            httpx.Response(200, json=[2]),
        ]
    )

    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return server(request)
        server.api_requests.append(request)
        return next(pages)

    api = Api(transport=_transport(handler))
    assert list(api.listing()) == [1, 2]
    assert server.api_tokens == ["Bearer token-1", "Bearer token-1"]


def test_graphql_routes_carry_the_token(transport, server):
    def handler(request):
        if str(request.url).startswith(TOKEN_URL):
            return server(request)
        server.api_requests.append(request)
        return httpx.Response(200, json={"data": {"viewer": {"login": "ann"}}})

    class Graph(Api):
        base_url = "https://api.test/graphql"

    assert Graph(transport=_transport(handler)).viewer() == {"viewer": {"login": "ann"}}
    assert server.api_tokens == ["Bearer token-1"]


def test_token_requests_go_through_the_mock_transport():
    mock = MockTransport()
    mock.on(path="/oauth/token").respond(httpx.Response(200, json={"access_token": "m"}))
    mock.on(path="/orders/1").respond(httpx.Response(200, json={"ok": True}))
    assert Api(transport=mock).get_order(id=1) == {"ok": True}
    token_call, api_call = mock.calls
    assert token_call.operation == "token"
    assert api_call.request.headers["Authorization"] == "Bearer m"


def test_instances_keep_their_own_tokens(transport, server):
    first, second = Api(transport=transport), Api("other", "s", transport=transport)
    first.get_order(id=1)
    second.get_order(id=1)
    assert server.api_tokens == ["Bearer token-1", "Bearer token-2"]


def test_the_token_url_must_be_a_web_url():
    with pytest.raises(ValueError, match="scheme"):
        OAuth2ClientCredentials("file:///etc/token", "id", "secret")


def test_clients_without_an_authenticator_send_no_authorization(recorder):
    from apiroute import HttpxClientTransport

    class Plain(Client):
        base_url = "https://api.test"
        get_x = route("/x")

    recorder.respond(httpx.Response(401), httpx.Response(200, json={}))
    plain = Plain(
        transport=HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder)))
    )
    with pytest.raises(UnexpectedResponse):
        plain.get_x()
    assert len(recorder.requests) == 1
    assert "authorization" not in recorder.last.headers


def _transport(handler):
    from apiroute import HttpxClientTransport

    return HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(handler)))
