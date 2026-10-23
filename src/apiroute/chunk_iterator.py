from contextlib import ExitStack
from typing import Any

import httpx


class ChunkIterator:
    """A streamed response body, chunk by chunk (what a stream="iter" route returns).

    The connection stays open until the chunks run out or close() is called; use it in a
    with block to be sure it closes when you stop early.
    """

    def __init__(self, response: httpx.Response, stack: ExitStack):
        self.response = response
        self._chunks = response.iter_bytes()
        self._stack = stack

    def __iter__(self) -> "ChunkIterator":
        return self

    def __next__(self) -> bytes:
        try:
            return next(self._chunks)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        self._stack.close()

    def __enter__(self) -> "ChunkIterator":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
