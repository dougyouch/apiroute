import httpx

from apiroute import (
    AsyncHttpxClientTransport,
    Client,
    HttpxClientTransport,
    OneShotTransport,
    route,
    shared_transports,
    use_transport,
)
from apiroute.auth import AccessToken, TokenAuthenticator
from apiroute.testing import MockTransport, mock_transport


class AcmeAuth(Client):
    base_url = "https://auth.acme.test"
    refresh = route("POST", "/session/refresh")


class AcmeTokens(TokenAuthenticator):
    """The README's example: a refresh endpoint that isn't OAuth."""

    def __init__(self, refresh_token):
        super().__init__()
        self.refresh_token = refresh_token

    def fetch_token(self, client):
        reply = AcmeAuth(**shared_transports(client)).refresh(
            body={"refreshToken": self.refresh_token}
        )
        self.refresh_token = reply["refreshToken"]
        return AccessToken(reply["token"], expires_at=reply["expiresAt"])


class Acme(Client):
    base_url = "https://api.acme.test"
    get_me = route("/me")

    def __init__(self, refresh_token, **kwargs):
        super().__init__(**kwargs)
        self.authenticator = AcmeTokens(refresh_token)


def test_gives_the_transports_a_client_was_given():
    sync = HttpxClientTransport(httpx.Client())
    async_ = AsyncHttpxClientTransport(httpx.AsyncClient())
    client = Client(transport=sync, async_transport=async_)
    assert shared_transports(client) == {"transport": sync, "async_transport": async_}


def test_gives_the_registered_transport_for_the_clients_class():
    class Api(Client):
        pass

    registered = OneShotTransport()
    use_transport(registered, Api)
    assert shared_transports(Api())["transport"] is registered


def test_a_helper_client_shares_the_mock_transport():
    mock = MockTransport()
    mock.on(path="/session/refresh").respond(
        httpx.Response(200, json={"token": "t", "refreshToken": "r2", "expiresAt": 4_000_000_000})
    )
    mock.on(path="/me").respond(httpx.Response(200, json={"name": "ann"}))
    api = Acme("r1", transport=mock)
    assert api.get_me() == {"name": "ann"}
    assert mock.calls[0].request.content == b'{"refreshToken": "r1"}'
    assert mock.calls[1].request.headers["Authorization"] == "Bearer t"
    assert api.authenticator.refresh_token == "r2"


def test_inside_mock_transport_every_client_is_answered_by_the_mock():
    with mock_transport() as mock:
        mock.on(path="/session/refresh").respond(
            httpx.Response(
                200, json={"token": "t", "refreshToken": "r2", "expiresAt": 4_000_000_000}
            )
        )
        mock.on(path="/me").respond(httpx.Response(200, json={}))
        Acme("r1").get_me()
    assert [call.request.url.path for call in mock.calls] == ["/session/refresh", "/me"]
