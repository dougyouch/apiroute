import httpx
import pytest

from apiroute.transports import (
    AsyncOneShotTransport,
    AsyncPooledTransport,
    OneShotTransport,
    PooledTransport,
    ThreadLocalTransport,
)
from tests.transports.conftest import spec


@pytest.mark.parametrize(
    "transport_class", [OneShotTransport, PooledTransport, ThreadLocalTransport]
)
def test_sync_transports_stream(recorder, mock, transport_class):
    recorder.respond(httpx.Response(200, content=iter([b"a", b"b"])))
    with transport_class(transport=mock).stream(spec()) as response:
        assert b"".join(response.iter_bytes()) == b"ab"


def test_one_shot_keeps_its_client_open_until_the_stream_is_done(mock, created_clients):
    with OneShotTransport(transport=mock).stream(spec()):
        assert not created_clients[0].is_closed
    assert created_clients[0].is_closed


@pytest.mark.anyio
@pytest.mark.parametrize("transport_class", [AsyncOneShotTransport, AsyncPooledTransport])
async def test_async_transports_stream(recorder, mock, transport_class):
    recorder.respond(httpx.Response(200, content=b"ab"))
    async with transport_class(transport=mock).stream(spec()) as response:
        assert b"".join([chunk async for chunk in response.aiter_bytes()]) == b"ab"
