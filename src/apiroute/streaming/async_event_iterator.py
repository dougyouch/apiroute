from collections import deque
from contextlib import AsyncExitStack
from typing import Any

import httpx

from apiroute.streaming.async_stream_reconnector import AsyncStreamReconnector
from apiroute.streaming.line_splitter import LineSplitter

NO_CONTENT = 204


class AsyncEventIterator:
    """The async counterpart of EventIterator, returned by stream="lines", "ndjson" and "sse"
    routes through .aio. Use it in an async with block to be sure the connection closes when
    you stop early."""

    def __init__(
        self,
        response: httpx.Response,
        stack: AsyncExitStack,
        decoder: Any,
        reconnector: AsyncStreamReconnector | None = None,
    ):
        self._decoder = decoder
        self._reconnector = reconnector
        self._items: deque[Any] = deque()
        self._lines: deque[str] = deque()
        self._finished = False
        self._failures = 0
        self._start(response, stack)

    def __aiter__(self) -> "AsyncEventIterator":
        return self

    async def __anext__(self) -> Any:
        try:
            while not self._items:
                await self._advance()
        except BaseException:
            await self.aclose()
            raise
        self._failures = 0
        return self._items.popleft()

    async def aclose(self) -> None:
        await self._stack.aclose()

    async def __aenter__(self) -> "AsyncEventIterator":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    def _start(self, response: httpx.Response, stack: AsyncExitStack) -> None:
        self.response = response
        self._stack = stack
        self._chunks = response.aiter_bytes()
        self._splitter = LineSplitter(self._decoder.encoding(response))
        self._body_done = response.status_code == NO_CONTENT

    async def _advance(self) -> None:
        if self._lines:
            self._items.extend(self._decoder.feed(self._lines.popleft()))
        elif not self._body_done:
            await self._pull()
        elif not self._finished:
            self._items.extend(self._decoder.end())
            self._finished = True
        else:
            raise StopAsyncIteration

    async def _pull(self) -> None:
        try:
            chunk = await self._chunks.__anext__()
        except StopAsyncIteration:
            self._lines.extend(self._splitter.finish())
            self._body_done = True
            return
        except Exception as error:
            if self._reconnector is None:
                raise
            await self._reconnect(error)
            return
        self._lines.extend(self._splitter.feed(chunk))

    async def _reconnect(self, error: Exception) -> None:
        assert self._reconnector is not None
        await self._stack.aclose()
        self._failures += 1
        self._decoder.reset()
        self._start(*await self._reconnector.reopen(error, self._failures, self._decoder))
