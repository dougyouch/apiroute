import pytest

from apiroute.transports.async_one_shot_transport import AsyncOneShotTransport
from tests.transports.conftest import spec

pytestmark = pytest.mark.anyio


async def test_uses_a_new_client_per_request_and_closes_it(recorder, mock, created_async_clients):
    transport = AsyncOneShotTransport(transport=mock)
    await transport.send(spec("/1"))
    await transport.send(spec("/2"))
    assert len(created_async_clients) == 2
    assert all(client.is_closed for client in created_async_clients)
    assert [request.url.path for request in recorder.requests] == ["/1", "/2"]
