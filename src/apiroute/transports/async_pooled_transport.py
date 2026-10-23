import asyncio
import os
import threading
import weakref
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.async_httpx_client_transport import AsyncHttpxClientTransport
from apiroute.transports.httpx_client_factory import HttpxClientFactory

# Event loops can't be weakly referenced under every runner; trio has no asyncio loop at all
_NO_ASYNCIO_LOOP = object()


class AsyncPooledTransport:
    """One httpx.AsyncClient, and so one connection pool, per event loop.

    An AsyncClient can't be shared across event loops, so each loop (one per thread, or one
    per asyncio.run) gets its own. After a fork the child opens its own clients.
    """

    def __init__(self, **httpx_options: Any):
        self._factory = HttpxClientFactory(**httpx_options)
        self._lock = threading.Lock()
        self._clients: weakref.WeakKeyDictionary[Any, httpx.AsyncClient] = (
            weakref.WeakKeyDictionary()
        )
        self._loopless_client: httpx.AsyncClient | None = None
        self._pid = os.getpid()

    async def send(self, spec: RequestSpec) -> httpx.Response:
        return await AsyncHttpxClientTransport(self._current_client()).send(spec)

    def stream(self, spec: RequestSpec) -> AbstractAsyncContextManager[httpx.Response]:
        return AsyncHttpxClientTransport(self._current_client()).stream(spec)

    async def aclose(self) -> None:
        """Closes the running loop's client; clients of other loops are dropped, as they can
        only be closed from their own loop."""
        with self._lock:
            client = self._pop_client(_current_loop())
            self._clients = weakref.WeakKeyDictionary()
            self._loopless_client = None
        if client is not None:
            await client.aclose()

    def _current_client(self) -> httpx.AsyncClient:
        loop = _current_loop()
        with self._lock:
            if self._pid != os.getpid():
                self._clients = weakref.WeakKeyDictionary()
                self._loopless_client = None
                self._pid = os.getpid()
            client = self._get_client(loop)
            if client is None:
                client = self._factory.new_async_client()
                self._set_client(loop, client)
            return client

    def _get_client(self, loop: Any) -> httpx.AsyncClient | None:
        if loop is _NO_ASYNCIO_LOOP:
            return self._loopless_client
        return self._clients.get(loop)

    def _set_client(self, loop: Any, client: httpx.AsyncClient) -> None:
        if loop is _NO_ASYNCIO_LOOP:
            self._loopless_client = client
        else:
            self._clients[loop] = client

    def _pop_client(self, loop: Any) -> httpx.AsyncClient | None:
        if loop is _NO_ASYNCIO_LOOP:
            return self._loopless_client
        return self._clients.pop(loop, None)


def _current_loop() -> Any:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return _NO_ASYNCIO_LOOP
