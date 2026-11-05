import pytest

from apiroute import Client, route
from apiroute.auth import AccessToken, AuthError, OAuth2RefreshToken
from tests.auth.conftest import TOKEN_URL, json_reply


class Api(Client):
    base_url = "https://api.test"

    def __init__(self, authenticator, **kwargs):
        super().__init__(**kwargs)
        self.authenticator = authenticator

    get_me = route("/me")


def refreshing(**kwargs):
    kwargs.setdefault("client_secret", "secret")
    return OAuth2RefreshToken(TOKEN_URL, "id", "refresh-0", **kwargs)


def test_trades_the_refresh_token_for_an_access_token(transport, server):
    Api(refreshing(), transport=transport).get_me()
    assert server.form() == {"grant_type": "refresh_token", "refresh_token": "refresh-0"}
    assert server.api_tokens == ["Bearer token-1"]


def test_a_rotated_refresh_token_replaces_the_old_one(transport, server):
    server.refresh_tokens = True
    saved = []
    auth = refreshing(on_refresh=saved.append)
    api = Api(auth, transport=transport)
    api.get_me()
    assert auth.refresh_token == "refresh-1"
    server.revoke()
    api.get_me()
    assert server.form()["refresh_token"] == "refresh-1"
    assert auth.refresh_token == "refresh-2"
    assert [(t.value, t.refresh_token) for t in saved] == [
        ("token-1", "refresh-1"),
        ("token-2", "refresh-2"),
    ]


def test_without_rotation_the_refresh_token_is_kept(transport, server):
    auth = refreshing()
    api = Api(auth, transport=transport)
    api.get_me()
    server.revoke()
    api.get_me()
    assert [server.form(i)["refresh_token"] for i in range(2)] == ["refresh-0", "refresh-0"]
    assert auth.refresh_token == "refresh-0"


def test_a_given_access_token_is_used_before_any_refresh(transport, server):
    server.valid.add("given")
    api = Api(refreshing(access_token=AccessToken("given", expires_in=600)), transport=transport)
    api.get_me()
    assert server.token_requests == []
    assert server.api_tokens == ["Bearer given"]


def test_a_given_access_token_the_api_rejects_is_refreshed(transport, server):
    api = Api(refreshing(access_token=AccessToken("stale")), transport=transport)
    assert api.get_me()["token"] == "token-1"
    assert server.api_tokens == ["Bearer stale", "Bearer token-1"]


def test_a_public_client_sends_only_its_id(transport, server):
    auth = OAuth2RefreshToken(TOKEN_URL, "app", "refresh-0")
    Api(auth, transport=transport).get_me()
    assert server.form() == {
        "grant_type": "refresh_token",
        "refresh_token": "refresh-0",
        "client_id": "app",
    }
    assert "authorization" not in server.token_requests[0].headers


def test_an_expired_refresh_token_raises_auth_error(transport, server):
    server.token_replies = [json_reply(400, {"error": "invalid_grant"})]
    with pytest.raises(AuthError) as raised:
        Api(refreshing(), transport=transport).get_me()
    assert raised.value.error == "invalid_grant"
    assert "refresh-0" not in str(raised.value)


@pytest.mark.anyio
async def test_async_refresh(async_transport, server):
    server.refresh_tokens = True
    auth = refreshing()
    assert (await Api(auth, async_transport=async_transport).aio.get_me())["token"] == "token-1"
    assert auth.refresh_token == "refresh-1"


def test_other_grants_subclass_the_token_authenticator(transport, server):
    from apiroute.auth import OAuth2TokenAuthenticator

    class JwtBearer(OAuth2TokenAuthenticator):
        def grant(self):
            return {"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": "j"}

    Api(JwtBearer(TOKEN_URL, "id", "secret"), transport=transport).get_me()
    assert server.form()["assertion"] == "j"


def test_grant_must_be_implemented(transport):
    from apiroute.auth import OAuth2TokenAuthenticator

    with pytest.raises(NotImplementedError):
        Api(OAuth2TokenAuthenticator(TOKEN_URL, "id", "s"), transport=transport).get_me()
