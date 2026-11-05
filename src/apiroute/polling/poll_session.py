from collections.abc import Callable
from typing import Any

import httpx

from apiroute.polling.poll import SEE_OTHER, Poll
from apiroute.polling.poll_step import PollStep
from apiroute.polling.poll_timeout import PollTimeout
from apiroute.response_reader import ResponseReader


class PollSession:
    """One poll= call's state and decisions, shared by the sync and async loops: which step
    comes next, where to send each poll, when time is up, and how to read the result.

    reader(decoder) makes a ResponseReader with the route's returns and converter, accepting
    any 2xx: decoder None parses JSON, or the route's decoder when it has one."""

    def __init__(
        self,
        poll: Poll,
        route_name: str,
        route_reader: ResponseReader,
        reader: Callable[[Any], ResponseReader],
        redact_url: Callable[[str], str],
    ):
        self._poll = poll
        self._route_name = route_name
        self._route_reader = route_reader
        self._reader = reader
        self._redact_url = redact_url
        self._origin: httpx.URL | None = None
        self._deadline: float | None = None
        self._polled = False

    def start(self, response: httpx.Response) -> PollStep:
        self._route_reader.check_status(response)
        self._origin = response.request.url
        if self._poll.timeout is not None:
            self._deadline = self._poll.clock() + self._poll.timeout
        return self._poll.first(response)

    def poll_url(self, step: PollStep) -> str:
        """The step's URL, resolved against the request's; checked for the time left when it's
        a wait, and refused when it's on another host than the request's."""
        assert self._origin is not None and step.url is not None
        url = self._origin.join(step.url)
        if (url.scheme, url.host, url.port) != (
            self._origin.scheme,
            self._origin.host,
            self._origin.port,
        ):
            raise ValueError(
                f"{self._route_name}: the operation's URL is on {url.scheme}://"
                f"{url.netloc.decode()}, not the request's; it wasn't followed"
            )
        if step.kind == "wait":
            self._check_time(step.delay, str(url))
        return str(url)

    def after(self, response: httpx.Response, url: str) -> PollStep:
        """The step after a poll's response; a status other than 2xx or 303 raises."""
        self._polled = True
        if response.status_code != SEE_OTHER:
            self._reader(None).check_status(response)
        return self._poll.next(response, url, self._route_name)

    def result(self, step: PollStep) -> Any:
        """The call's result from a done step: the route's own reading when nothing was polled,
        else the finished status body (at the Poll's result path)."""
        assert step.response is not None
        if not self._polled:
            return self._route_reader.read(step.response)
        return self._reader(self._poll.decode).read(step.response)

    def fetched(self, response: httpx.Response) -> Any:
        """The result fetched from a result URL or a 303's Location."""
        return self._reader(None).read(response)

    def _check_time(self, delay: float, url: str) -> None:
        if self._deadline is not None and self._poll.clock() + delay > self._deadline:
            assert self._poll.timeout is not None
            raise PollTimeout(self._route_name, self._poll.timeout, self._redact_url(url))
