import httpx
import pytest

from apiroute import Client, OneShotTransport, route
from apiroute.testing import MockTransport, NetworkBlocked, block_network

pytestmark = pytest.mark.anyio


class Api(Client):
    base_url = "https://x.test"

    @route("/a")
    def get_a(self): ...


def test_a_real_request_is_refused():
    with block_network(), pytest.raises(NetworkBlocked, match="GET https://x.test/a"):
        Api(transport=OneShotTransport()).get_a()


async def test_a_real_async_request_is_refused():
    with block_network(), pytest.raises(NetworkBlocked):
        await Api().aio.get_a()


def test_mocks_still_answer():
    mock = MockTransport().respond(httpx.Response(200, json="ok"))
    with block_network():
        assert Api(transport=mock).get_a() == "ok"
        assert httpx.Client(transport=httpx.MockTransport(httpx.Response)).get("https://x.test")


def test_the_real_transports_come_back_on_exit():
    original = httpx.HTTPTransport.handle_request
    with block_network():
        assert httpx.HTTPTransport.handle_request is not original
    assert httpx.HTTPTransport.handle_request is original
