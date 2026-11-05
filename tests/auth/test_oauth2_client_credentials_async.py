import asyncio

import pytest

from apiroute import Client, UnexpectedResponse, route
from apiroute.auth import AuthError, OAuth2ClientCredentials
from tests.auth.conftest import TOKEN_URL, json_reply

pytestmark = pytest.mark.anyio


class Api(Client):
    base_url = "https://api.test"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.authenticator = OAuth2ClientCredentials(TOKEN_URL, "id", "secret")

    get_order = route("/orders/{id}")
    feed = route("/stream", stream="sse")


@pytest.fixture
def api(async_transport):
    return Api(async_transport=async_transport)


async def test_fetches_a_token_and_sends_it(api, server):
    assert (await api.aio.get_order(id=1))["token"] == "token-1"
    assert server.form() == {"grant_type": "client_credentials"}


async def test_concurrent_calls_fetch_one_token(api, server):
    results = await asyncio.gather(*[api.aio.get_order(id=n) for n in range(10)])
    assert {r["token"] for r in results} == {"token-1"}
    assert len(server.token_requests) == 1


async def test_a_401_refreshes_and_sends_once_more(api, server):
    await api.aio.get_order(id=1)
    server.revoke()
    assert (await api.aio.get_order(id=2))["token"] == "token-2"
    assert server.api_tokens == ["Bearer token-1", "Bearer token-1", "Bearer token-2"]


async def test_a_second_401_is_raised(api, server):
    server.token_replies = [json_reply(200, {"access_token": "bogus"})] * 2
    with pytest.raises(UnexpectedResponse):
        await api.aio.get_order(id=1)
    assert len(server.token_requests) == 2


async def test_a_refused_token_request_raises_auth_error(api, server):
    server.token_replies = [json_reply(400, {"error": "invalid_scope"})]
    with pytest.raises(AuthError) as raised:
        await api.aio.get_order(id=1)
    assert raised.value.error == "invalid_scope"


async def test_streams_refresh_on_401(api, server):
    await api.aio.get_order(id=1)
    server.revoke()
    events = await api.aio.feed()
    assert [event.data async for event in events] == ["ok"]
    assert server.api_tokens[-1] == "Bearer token-2"


async def test_sync_and_async_calls_share_the_token(api, server, transport):
    api._transport = transport
    await api.aio.get_order(id=1)
    api.get_order(id=2)
    assert len(server.token_requests) == 1
