import httpx
import pytest

from apiroute import Client, HttpxClientTransport, Retries, route, use_transport
from apiroute.testing import mock_transport
from apiroute.transport_configuration import ASYNC_TRANSPORTS, TRANSPORTS


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=3, sleep=1, backoff=2)

    @route("/a")
    def get_a(self): ...


def test_every_client_sends_to_the_mock_even_a_registered_class(recorder, transport):
    use_transport(transport, Api)
    with mock_transport() as mock:
        mock.respond(httpx.Response(200, json="mocked"))
        assert Api().get_a() == "mocked"
    assert recorder.requests == []


def test_registrations_come_back_on_exit(transport):
    use_transport(transport, Api)
    before = TRANSPORTS.snapshot(), ASYNC_TRANSPORTS.snapshot()
    with mock_transport():
        pass
    assert (TRANSPORTS.snapshot(), ASYNC_TRANSPORTS.snapshot()) == before
    assert TRANSPORTS.for_class(Api) is transport


def test_registrations_come_back_when_the_block_raises(transport):
    use_transport(transport)
    with pytest.raises(ZeroDivisionError), mock_transport():
        raise ZeroDivisionError
    assert TRANSPORTS.for_class(Api) is transport


def test_an_instance_transport_is_kept(recorder, transport):
    with mock_transport():
        Api(transport=transport).get_a()
    assert len(recorder.requests) == 1


@pytest.mark.anyio
async def test_async_calls_send_to_the_mock():
    with mock_transport() as mock:
        mock.respond(httpx.Response(200, json="async"))
        assert await Api().aio.get_a() == "async"


def test_retries_record_their_waits_instead_of_sleeping():
    with mock_transport() as mock:
        mock.respond(httpx.ConnectError("a"), httpx.ConnectError("b"), httpx.Response(200))
        Api().get_a()
    assert mock.sleeps == [1, 2]


def test_unused_queued_responses_fail_the_block():
    with pytest.raises(AssertionError, match="1 queued mock responses were never requested"):
        with mock_transport() as mock:
            mock.respond(httpx.Response(200))


def test_unused_queued_responses_can_be_allowed():
    with mock_transport(assert_all_used=False) as mock:
        mock.respond(httpx.Response(200))


def test_a_handler_answers_unmatched_requests():
    with mock_transport(lambda request: httpx.Response(200, json="handled")):
        assert Api().get_a() == "handled"


def test_the_mock_is_a_transport_for_use_transport(recorder):
    transport = HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(recorder)))
    with mock_transport() as mock:
        use_transport(transport, Api)
        Api().get_a()
        assert mock.calls == []
    assert TRANSPORTS.for_class(Api) is not transport
