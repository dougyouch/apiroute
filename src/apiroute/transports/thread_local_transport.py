import os
import threading
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.httpx_client_factory import HttpxClientFactory
from apiroute.transports.httpx_client_transport import HttpxClientTransport


class _ThreadClient:
    """One thread's client; closed when the thread ends and its thread-local data is freed."""

    def __init__(self, http_client: httpx.Client):
        self.http_client = http_client
        self.pid = os.getpid()
        self.finalizer = weakref.finalize(self, http_client.close)


class ThreadLocalTransport:
    """An httpx.Client per thread, so no thread ever waits on another's connections.

    Suits a fixed set of worker threads that each make their own requests. With many
    short-lived threads, prefer PooledTransport. After a fork the child opens its own clients.
    """

    def __init__(self, **httpx_options: Any):
        self._factory = HttpxClientFactory(**httpx_options)
        self._local = threading.local()
        self._thread_clients: weakref.WeakSet[_ThreadClient] = weakref.WeakSet()

    def send(self, spec: RequestSpec) -> httpx.Response:
        return HttpxClientTransport(self._current_client().http_client).send(spec)

    @contextmanager
    def stream(self, spec: RequestSpec) -> Iterator[httpx.Response]:
        # Holding the thread's client here keeps it from being closed mid-stream, even if
        # nothing else still references this transport
        thread_client = self._current_client()
        with HttpxClientTransport(thread_client.http_client).stream(spec) as response:
            yield response

    def close(self) -> None:
        """Closes every thread's client; each thread opens a new one on its next request."""
        for thread_client in list(self._thread_clients):
            if thread_client.pid == os.getpid():
                thread_client.finalizer()
        self._local = threading.local()

    def _current_client(self) -> _ThreadClient:
        thread_client = getattr(self._local, "client", None)
        if thread_client is None or thread_client.pid != os.getpid():
            thread_client = _ThreadClient(self._factory.new_client())
            self._local.client = thread_client
            self._thread_clients.add(thread_client)
        return thread_client
