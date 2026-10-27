import httpx
import pytest

from apiroute import Client, OneShotTransport, route
from apiroute.testing import MockTransport, NetworkBlocked


class Api(Client):
    base_url = "https://x.test"

    @route("/a")
    def get_a(self): ...


def test_apiroute_mock_answers_every_client(apiroute_mock):
    assert isinstance(apiroute_mock, MockTransport)
    apiroute_mock.respond(httpx.Response(200, json="ok"))
    assert Api().get_a() == "ok"


def test_apiroute_block_network_refuses_real_requests(apiroute_block_network):
    with pytest.raises(NetworkBlocked):
        Api(transport=OneShotTransport()).get_a()
