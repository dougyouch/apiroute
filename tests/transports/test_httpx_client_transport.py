import httpx

from apiroute.transports.httpx_client_transport import HttpxClientTransport
from tests.transports.conftest import spec


def test_sends_the_spec(recorder, mock):
    http_client = httpx.Client(transport=mock)
    HttpxClientTransport(http_client).send(spec())
    request = recorder.last
    assert str(request.url) == "https://x.test/a?q=1"
    assert request.headers["X-A"] == "1"
    assert request.extensions["timeout"]["read"] == 5


def test_close_leaves_the_owners_client_open(mock):
    http_client = httpx.Client(transport=mock)
    HttpxClientTransport(http_client).close()
    assert not http_client.is_closed
