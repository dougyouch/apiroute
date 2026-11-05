import httpx
import pytest

from apiroute import Client, Section, route
from apiroute.call_context import CallContext
from apiroute.testing import MockTransport


def recording(seen):
    def handler(request):
        context = CallContext.current()
        seen.append((type(context.router).__name__, context.definition.name))
        return httpx.Response(200, json={})

    return handler


class Api(Client):
    base_url = "https://x.test"
    get_x = route("/x")

    class admin(Section):
        get_y = route("/y")


def test_requests_are_sent_inside_their_calls_context():
    seen = []
    api = Api(transport=MockTransport(recording(seen)))
    api.get_x()
    api.admin.get_y()
    assert seen == [("Api", "get_x"), ("admin", "get_y")]


def test_there_is_none_outside_a_call():
    assert CallContext.current() is None
    Api(transport=MockTransport(recording([]))).get_x()
    assert CallContext.current() is None


def test_a_call_made_inside_another_has_its_own_and_restores_the_outer():
    seen = []

    class Outer(Api):
        def on_request(self, request):
            if request.operation == "get_x":
                self.admin.get_y()  # e.g. an authenticator fetching a token
            seen.append(CallContext.current().definition.name)

    Outer(transport=MockTransport(lambda request: httpx.Response(200, json={}))).get_x()
    assert seen == ["get_y", "get_x"]


def test_it_is_reset_when_the_call_fails():
    api = Api(transport=MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(Exception, match="500"):
        api.get_x()
    assert CallContext.current() is None


@pytest.mark.anyio
async def test_async_calls():
    seen = []
    mock = MockTransport(recording(seen))
    api = Api(async_transport=mock.aio)
    await api.aio.admin.get_y()
    assert seen == [("admin", "get_y")]
    assert CallContext.current() is None
