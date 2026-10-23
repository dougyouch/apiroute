import inspect
from collections.abc import Callable, Iterator
from contextlib import AsyncExitStack, ExitStack, contextmanager
from typing import Any

import httpx

from apiroute.async_chunk_iterator import AsyncChunkIterator
from apiroute.chunk_iterator import ChunkIterator
from apiroute.request_spec import RequestSpec
from apiroute.response_reader import ResponseReader
from apiroute.stream_path_validator import validate_stream_path


class StreamReader:
    """Opens a streamed response, checks its status before any body is read, then hands the
    body to a file, a writable object or an iterator.

    A rejected response's body is read in full instead, so UnexpectedResponse can show it,
    and nothing is written: an existing file is left untouched.
    """

    def __init__(self, status: ResponseReader, mode: str, destination: Any):
        self._status = status
        self._mode = mode
        # A bad path fails here, before the request is sent
        self._destination = validate_stream_path(destination) if mode == "file" else destination

    def open(self, transport: Any, spec: RequestSpec) -> tuple[httpx.Response, ExitStack]:
        stack = ExitStack()
        response = stack.enter_context(transport.stream(spec))
        try:
            if not self._status.is_expected(response.status_code):
                response.read()
            self._status.check_status(response)
        except BaseException:
            stack.close()
            raise
        return response, stack

    def consume(self, response: httpx.Response, stack: ExitStack) -> Any:
        if self._mode == "iter":
            return ChunkIterator(response, stack)
        with stack, self._writer() as write:
            for chunk in response.iter_bytes():
                write(chunk)
        return response

    async def open_async(
        self, transport: Any, spec: RequestSpec
    ) -> tuple[httpx.Response, AsyncExitStack]:
        stack = AsyncExitStack()
        response = await stack.enter_async_context(transport.stream(spec))
        try:
            if not self._status.is_expected(response.status_code):
                await response.aread()
            self._status.check_status(response)
        except BaseException:
            await stack.aclose()
            raise
        return response, stack

    async def consume_async(self, response: httpx.Response, stack: AsyncExitStack) -> Any:
        if self._mode == "iter":
            return AsyncChunkIterator(response, stack)
        async with stack:
            with self._writer() as write:
                async for chunk in response.aiter_bytes():
                    written = write(chunk)
                    if inspect.isawaitable(written):  # e.g. an aiofiles file
                        await written
        return response

    @contextmanager
    def _writer(self) -> Iterator[Callable[[bytes], Any]]:
        """The write function for each chunk: the file's, opened only now that the status has
        passed, or the caller's object's, which is theirs to close."""
        if self._mode == "file":
            with open(self._destination, "wb") as file:
                yield file.write
        else:
            yield self._destination.write
