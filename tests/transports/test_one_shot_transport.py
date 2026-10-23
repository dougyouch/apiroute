from apiroute.transports.one_shot_transport import OneShotTransport
from tests.transports.conftest import spec


def test_uses_a_new_client_per_request_and_closes_it(recorder, mock, created_clients):
    transport = OneShotTransport(transport=mock)
    first = transport.send(spec("/1"))
    transport.send(spec("/2"))
    assert first.status_code == 200
    assert len(created_clients) == 2
    assert all(client.is_closed for client in created_clients)
    assert [request.url.path for request in recorder.requests] == ["/1", "/2"]
