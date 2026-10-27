import httpx
import pytest

from apiroute import Client, route
from apiroute.testing import MockTransport, UnmatchedRequest

pytestmark = pytest.mark.anyio


class Api(Client):
    base_url = "https://x.test"

    @route("/users/{username}", operation="getUser")
    def get_user(self, username: str): ...

    @route("/events", stream="iter")
    def get_events(self): ...


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def api(mock):
    return Api(transport=mock, async_transport=mock.aio)


async def test_async_calls_answer_from_the_same_mock(api, mock):
    mock.on(operation="getUser").respond(httpx.Response(200, json="user"))
    assert await api.aio.get_user("a") == "user"
    assert api.get_user("b") == "user"
    assert [call.path for call in mock.calls] == ["/users/a", "/users/b"]


async def test_async_streams_read_the_mock_body(api, mock):
    mock.respond(httpx.Response(200, content=b"abcd"))
    chunks = [chunk async for chunk in await api.aio.get_events()]
    assert b"".join(chunks) == b"abcd"


async def test_an_unmatched_async_request_fails(api):
    with pytest.raises(UnmatchedRequest):
        await api.aio.get_user("a")
