import os
import threading
from contextlib import AbstractContextManager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.httpx_client_factory import HttpxClientFactory
from apiroute.transports.httpx_client_transport import HttpxClientTransport


class PooledTransport:
    """One httpx.Client, and so one connection pool, shared by every thread in the process.

    Size it with httpx_options such as limits=httpx.Limits(max_connections=20); add
    http2=True (with the httpx[http2] extra) to multiplex requests over one connection.
    After a fork the child opens its own client and leaves the parent's alone.
    """

    def __init__(self, **httpx_options: Any):
        self._factory = HttpxClientFactory(**httpx_options)
        self._lock = threading.Lock()
        self._http_client: httpx.Client | None = None
        self._pid: int | None = None

    def send(self, spec: RequestSpec) -> httpx.Response:
        return HttpxClientTransport(self._current_client()).send(spec)

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        return HttpxClientTransport(self._current_client()).stream(spec)

    def close(self) -> None:
        with self._lock:
            if self._http_client is not None and self._pid == os.getpid():
                self._http_client.close()
            self._http_client = None

    def _current_client(self) -> httpx.Client:
        with self._lock:
            if self._http_client is None or self._pid != os.getpid():
                self._http_client = self._factory.new_client()
                self._pid = os.getpid()
            return self._http_client
