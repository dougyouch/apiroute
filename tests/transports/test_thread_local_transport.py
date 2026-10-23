import gc
import threading

from apiroute.transports.thread_local_transport import ThreadLocalTransport
from tests.transports.conftest import spec


def send_in_thread(transport):
    thread = threading.Thread(target=transport.send, args=(spec(),))
    thread.start()
    thread.join()


def test_one_client_per_thread(mock, created_clients):
    transport = ThreadLocalTransport(transport=mock)
    transport.send(spec())
    transport.send(spec())
    send_in_thread(transport)
    assert len(created_clients) == 2


def test_a_finished_threads_client_is_closed(mock, created_clients):
    transport = ThreadLocalTransport(transport=mock)
    send_in_thread(transport)
    gc.collect()
    assert created_clients[0].is_closed


def test_close_closes_every_threads_client(mock, created_clients):
    transport = ThreadLocalTransport(transport=mock)
    transport.send(spec())
    transport.close()
    assert created_clients[0].is_closed
    transport.send(spec())
    assert len(created_clients) == 2
