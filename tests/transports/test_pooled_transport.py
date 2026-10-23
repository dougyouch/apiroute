import threading

from apiroute.transports import pooled_transport
from apiroute.transports.pooled_transport import PooledTransport
from tests.transports.conftest import spec


def test_shares_one_client_across_requests_and_threads(mock, created_clients):
    transport = PooledTransport(transport=mock)
    transport.send(spec())
    thread = threading.Thread(target=transport.send, args=(spec(),))
    thread.start()
    thread.join()
    assert len(created_clients) == 1


def test_opens_a_new_client_after_a_fork(mock, created_clients, monkeypatch):
    transport = PooledTransport(transport=mock)
    transport.send(spec())
    monkeypatch.setattr(pooled_transport.os, "getpid", lambda: -1)
    transport.send(spec())
    assert len(created_clients) == 2
    assert not created_clients[0].is_closed  # the parent's client is the parent's to close


def test_close_closes_the_client_and_the_next_request_opens_another(mock, created_clients):
    transport = PooledTransport(transport=mock)
    transport.send(spec())
    transport.close()
    assert created_clients[0].is_closed
    transport.send(spec())
    assert len(created_clients) == 2
