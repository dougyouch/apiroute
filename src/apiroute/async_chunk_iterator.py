from contextlib import AsyncExitStack
from typing import Any

import httpx


class AsyncChunkIterator:
    """The async counterpart of ChunkIterator, returned by stream="iter" routes through .aio.

    Use it in an async with block to be sure the connection closes when you stop early.
    """

    def __init__(self, response: httpx.Response, stack: AsyncExitStack):
        self.response = response
        self._chunks = response.aiter_bytes()
        self._stack = stack

    def __aiter__(self) -> "AsyncChunkIterator":
        return self

    async def __anext__(self) -> bytes:
        try:
            return await self._chunks.__anext__()
        except BaseException:
            await self.aclose()
            raise

    async def aclose(self) -> None:
        await self._stack.aclose()

    async def __aenter__(self) -> "AsyncChunkIterator":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()
