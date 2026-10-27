"""Retry safety against a real, misbehaving local server: the exceptions httpx raises for a
stalled or dropped connection, and how many requests actually reach the server."""

import asyncio
import socket
import threading
import time

import httpx
import pytest

from apiroute import Client, Retries, route


class MisbehavingServer:
    """Reads each request, then: "stall" never answers, "drop" closes the connection."""

    def __init__(self, mode: str):
        self.mode = mode
        self.requests: list[tuple[str, str | None]] = []
        self._socket = socket.socket()
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(16)
        self.url = f"http://127.0.0.1:{self._socket.getsockname()[1]}"
        threading.Thread(target=self._serve, daemon=True).start()

    def close(self) -> None:
        self._socket.close()

    def _serve(self) -> None:
        while True:
            try:
                connection, _ = self._socket.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(connection,), daemon=True).start()

    def _handle(self, connection: socket.socket) -> None:
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = connection.recv(4096)
            if not chunk:
                return
            data += chunk
        lines = data.split(b"\r\n\r\n")[0].decode().split("\r\n")
        key = next(
            (
                line.split(":", 1)[1].strip()
                for line in lines
                if line.lower().startswith("idempotency-key:")
            ),
            None,
        )
        self.requests.append((lines[0].split()[0], key))
        if self.mode == "stall":
            time.sleep(1)
        connection.close()


def client_for(server: MisbehavingServer, key: str | None = None) -> Client:
    class Api(Client):
        base_url = server.url
        retries = Retries(attempts=3, sleep=0)
        timeout = 0.1
        idempotency_key = key

        @route("GET", "/x")
        def read(self): ...

        @route("POST", "/x")
        def write(self): ...

        @route("POST", "/x", idempotent=True)
        def safe_write(self): ...

    return Api()


@pytest.fixture(params=["stall", "drop"])
def server(request):
    server = MisbehavingServer(request.param)
    yield server
    server.close()


def call(method) -> type[Exception]:
    with pytest.raises((httpx.ReadTimeout, httpx.RemoteProtocolError)) as caught:
        method()
    time.sleep(0.05)  # let the server thread record the last request
    return caught.type


@pytest.mark.parametrize("name, requests", [("read", 3), ("write", 1), ("safe_write", 3)])
def test_requests_that_reach_the_server(server, name, requests):
    error = call(getattr(client_for(server), name))
    assert error is (httpx.ReadTimeout if server.mode == "stall" else httpx.RemoteProtocolError)
    assert len(server.requests) == requests


def test_a_keyed_post_is_retried_with_the_same_key(server):
    call(client_for(server, "Idempotency-Key").write)
    keys = [key for _, key in server.requests]
    assert len(keys) == 3 and keys[0] is not None and len(set(keys)) == 1


def test_async_post_reaches_the_server_once(server):
    call(lambda: asyncio.run(client_for(server).aio.write()))
    assert len(server.requests) == 1


def test_a_refused_connection_is_retried_for_post():
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    attempts = []

    class Api(Client):
        base_url = f"http://127.0.0.1:{port}"
        retries = Retries(attempts=3, sleep=0)

        @route("POST", "/x")
        def write(self): ...

        def should_retry(self, error, attempt):
            attempts.append(type(error))
            return super().should_retry(error, attempt)

    with pytest.raises(httpx.ConnectError):
        Api().write()
    assert attempts == [httpx.ConnectError, httpx.ConnectError]  # asked after attempts 1 and 2
