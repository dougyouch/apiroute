import httpx
import pytest

from apiroute.transports.async_httpx_client_transport import AsyncHttpxClientTransport
from tests.transports.conftest import spec

pytestmark = pytest.mark.anyio


async def test_sends_the_spec(recorder, mock):
    await AsyncHttpxClientTransport(httpx.AsyncClient(transport=mock)).send(spec())
    assert str(recorder.last.url) == "https://x.test/a?q=1"
    assert recorder.last.headers["X-A"] == "1"


async def test_aclose_leaves_the_owners_client_open(mock):
    http_client = httpx.AsyncClient(transport=mock)
    await AsyncHttpxClientTransport(http_client).aclose()
    assert not http_client.is_closed
