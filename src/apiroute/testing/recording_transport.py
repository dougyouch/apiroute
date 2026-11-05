from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any

import httpx

from apiroute.request_spec import RequestSpec


class RecordingTransport:
    """Sends through a real transport and hands each response to record(response). A streamed
    response is read in full first, so what is recorded is all of it."""

    def __init__(self, inner: Any, record: Callable[[httpx.Response], None]):
        self._inner = inner
        self._record = record

    def send(self, spec: RequestSpec) -> httpx.Response:
        response = self._inner.send(spec)
        self._record(response)
        return response

    def stream(self, spec: RequestSpec) -> AbstractContextManager[httpx.Response]:
        return self._stream(spec)

    @contextmanager
    def _stream(self, spec: RequestSpec) -> Iterator[httpx.Response]:
        with self._inner.stream(spec) as response:
            response.read()
            self._record(response)
            yield response

    def close(self) -> None:
        self._inner.close()
