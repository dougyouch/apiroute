from collections import deque
from contextlib import ExitStack
from typing import Any

import httpx

from apiroute.streaming.line_splitter import LineSplitter
from apiroute.streaming.stream_reconnector import StreamReconnector

NO_CONTENT = 204


class EventIterator:
    """What a stream="lines", "ndjson" or "sse" route returns: the body's lines, JSON values or
    events, each as soon as it has arrived. Lines are decoded one at a time, so the items
    before a line that fails to decode are yielded before its error is raised.

    The connection stays open until the body ends or close() is called; use it in a with block
    to be sure it closes when you stop early. An SSE stream whose connection fails mid-body
    reconnects as the route's retries allow, resuming from the last event ID.
    """

    def __init__(
        self,
        response: httpx.Response,
        stack: ExitStack,
        decoder: Any,
        reconnector: StreamReconnector | None = None,
    ):
        self._decoder = decoder
        self._reconnector = reconnector
        self._items: deque[Any] = deque()
        self._lines: deque[str] = deque()
        self._finished = False
        self._failures = 0
        self._start(response, stack)

    def __iter__(self) -> "EventIterator":
        return self

    def __next__(self) -> Any:
        try:
            while not self._items:
                self._advance()
        except BaseException:
            self.close()
            raise
        self._failures = 0
        return self._items.popleft()

    def close(self) -> None:
        self._stack.close()

    def __enter__(self) -> "EventIterator":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def _start(self, response: httpx.Response, stack: ExitStack) -> None:
        self.response = response
        self._stack = stack
        self._chunks = response.iter_bytes()
        self._splitter = LineSplitter(self._decoder.encoding(response))
        # A 204 is an event stream's way of saying "stop"
        self._body_done = response.status_code == NO_CONTENT

    def _advance(self) -> None:
        """One step toward the next item: decode a line, end the stream, or read a chunk."""
        if self._lines:
            self._items.extend(self._decoder.feed(self._lines.popleft()))
        elif not self._body_done:
            self._pull()
        elif not self._finished:
            self._items.extend(self._decoder.end())
            self._finished = True
        else:
            raise StopIteration

    def _pull(self) -> None:
        try:
            chunk = next(self._chunks)
        except StopIteration:
            self._lines.extend(self._splitter.finish())
            self._body_done = True
            return
        except Exception as error:
            if self._reconnector is None:
                raise
            self._reconnect(error)
            return
        self._lines.extend(self._splitter.feed(chunk))

    def _reconnect(self, error: Exception) -> None:
        """Every line received has been decoded by now: a chunk is read only once they are."""
        assert self._reconnector is not None
        self._stack.close()
        self._failures += 1
        self._decoder.reset()
        self._start(*self._reconnector.reopen(error, self._failures, self._decoder))
