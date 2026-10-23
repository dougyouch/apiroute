import httpx
import pytest

from apiroute import (
    AsyncHttpxClientTransport,
    AsyncOneShotTransport,
    Client,
    HttpxClientTransport,
    OneShotTransport,
    aclose_transports,
    close_transports,
    route,
    use_transport,
)
from apiroute.transport_configuration import ASYNC_TRANSPORTS, TRANSPORTS


class Api(Client):
    base_url = "https://x.test"

    @route("/things")
    def get_things(self): ...


def test_use_transport_for_a_class_reaches_its_requests(recorder):
    use_transport(HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder))), Api)
    Api().get_things()
    assert str(recorder.last.url) == "https://x.test/things"


def test_an_instance_transport_wins_over_the_registry(recorder, transport):
    use_transport(
        HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(lambda r: 1 / 0)))
    )
    Api(transport=transport).get_things()
    assert len(recorder.requests) == 1


def test_async_and_sync_transports_go_to_their_own_registries(recorder):
    mock = httpx.MockTransport(recorder)
    use_transport(AsyncHttpxClientTransport(httpx.AsyncClient(transport=mock)), Api)
    assert isinstance(TRANSPORTS.for_class(Api), OneShotTransport)
    assert isinstance(ASYNC_TRANSPORTS.for_class(Api), AsyncHttpxClientTransport)


def test_defaults_are_one_shot_on_both_sides():
    assert isinstance(TRANSPORTS.for_class(Api), OneShotTransport)
    assert isinstance(ASYNC_TRANSPORTS.for_class(Api), AsyncOneShotTransport)


class Closing:
    def __init__(self):
        self.closed = False

    def send(self, spec): ...

    def close(self):
        self.closed = True


class AsyncClosing:
    def __init__(self):
        self.closed = False

    async def send(self, spec): ...

    async def aclose(self):
        self.closed = True


@pytest.mark.anyio
async def test_close_and_aclose_transports():
    sync, async_ = Closing(), AsyncClosing()
    use_transport(sync)
    use_transport(async_)
    close_transports()
    assert sync.closed and not async_.closed
    await aclose_transports()
    assert async_.closed
