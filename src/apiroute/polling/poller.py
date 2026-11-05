from collections.abc import Callable
from typing import Any

import httpx

from apiroute.polling.poll_session import PollSession


class Poller:
    """Runs a poll= call: the route's request, then GETs of the operation's status URL, with
    waits between them, until it is done."""

    def __init__(self, session: PollSession, sleep: Callable[[float], Any]):
        self._session = session
        self._sleep = sleep

    def run(self, send: Callable[[], httpx.Response], get: Callable[[str], httpx.Response]) -> Any:
        session = self._session
        step = session.start(send())
        while step.kind == "wait":
            url = session.poll_url(step)
            self._sleep(step.delay)
            step = session.after(get(url), url)
        if step.kind == "fetch":
            return session.fetched(get(session.poll_url(step)))
        return session.result(step)
