from typing import Any

import httpx

from apiroute.streaming.stream_reconnector import StreamReconnector


class AsyncStreamReconnector(StreamReconnector):
    """StreamReconnector for async streams: the sleep and the reopen are awaited."""

    async def reopen(  # type: ignore[override]
        self, error: Exception, attempt: int, decoder: Any
    ) -> tuple[httpx.Response, Any]:
        await self._sleep(self.delay(error, attempt, decoder))
        return await self._reopen(self.resume_headers(decoder))
