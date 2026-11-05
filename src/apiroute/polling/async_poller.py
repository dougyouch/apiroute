from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from apiroute.polling.poll_session import PollSession


class AsyncPoller:
    """Poller for async calls: the requests and waits are awaited."""

    def __init__(self, session: PollSession, sleep: Callable[[float], Awaitable[Any]]):
        self._session = session
        self._sleep = sleep

    async def run(
        self,
        send: Callable[[], Awaitable[httpx.Response]],
        get: Callable[[str], Awaitable[httpx.Response]],
    ) -> Any:
        session = self._session
        step = session.start(await send())
        while step.kind == "wait":
            url = session.poll_url(step)
            await self._sleep(step.delay)
            step = session.after(await get(url), url)
        if step.kind == "fetch":
            return session.fetched(await get(session.poll_url(step)))
        return session.result(step)
