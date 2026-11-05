import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from apiroute.pagination.dotted_path import DottedPath
from apiroute.polling.operation_failed import OperationFailed
from apiroute.polling.poll_step import PollStep

ACCEPTED, SEE_OTHER = 202, 303
# Headers that name a status URL to poll even on a 200 or 201 (Azure's PUT and PATCH);
# Location on a 201 is where a created resource is, not an operation
ASYNC_HEADERS = ("operation-location", "azure-asyncoperation")


@dataclass(frozen=True)
class Poll:
    """How a poll= route waits for a long-running operation (the "202 Accepted" pattern):

        @route("POST", "/v1/exports", poll=Poll(interval=2, timeout=600))
        def export(self, body: dict) -> Export: ...

    When the response is a 202 with a status URL in one of `headers` (or a 200 or 201 with an
    Operation-Location or Azure-AsyncOperation header), the method GETs that URL every
    `interval` seconds, or after the response's Retry-After when longer, until:

    - the status body's `status` field (a dotted path) is in `succeeded` (or is true, as
      Google's `done` is): its body, or the value at the dotted path `result`, is the result;
      or, when `result_url` names a URL in it, the body at that URL is,
    - the status is in `failed`, or the `error` field is set: OperationFailed is raised,
    - a status response has no status field: it is the result,
    - a 303 See Other names where the result is: that is fetched.

    Statuses compare without case. A response that isn't a 202 is the result, as it would be
    without poll=. PollTimeout is raised once `timeout` seconds have passed (None waits for
    ever). Polls are GETs with the client's headers, auth and hooks, retried as reads are, and
    a status URL on another host than the request's is refused rather than sent credentials.
    """

    interval: float = 1.0
    timeout: float | None = 600.0
    status: str | None = "status"
    succeeded: tuple[str, ...] = (
        "succeeded",
        "success",
        "successful",
        "completed",
        "complete",
        "done",
        "finished",
    )
    failed: tuple[str, ...] = (
        "failed",
        "failure",
        "canceled",
        "cancelled",
        "error",
        "errored",
        "aborted",
    )
    error: str | None = None
    result: str | None = None
    result_url: str | None = None
    headers: tuple[str, ...] = ("Operation-Location", "Azure-AsyncOperation", "Location")
    clock: Callable[[], float] = field(default=time.monotonic, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.interval < 0:
            raise ValueError("interval must be 0 or more seconds")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be more than 0 seconds, or None")

    def first(self, response: httpx.Response) -> PollStep:
        """The step after the route's own response."""
        url = self._status_url(response)
        if url is None:
            return PollStep("done", response=response)
        if response.status_code == ACCEPTED or self._names_operation(response):
            return PollStep("wait", url, self._delay(response))
        return PollStep("done", response=response)

    def next(self, response: httpx.Response, url: str, route_name: str) -> PollStep:
        """The step after a status response from polling url."""
        if response.status_code == SEE_OTHER and "location" in response.headers:
            return PollStep("fetch", response.headers["location"])
        if response.status_code == ACCEPTED:
            return PollStep("wait", self._status_url(response) or url, self._delay(response))
        body = _json(response)
        if self.error is not None and DottedPath(self.error).read(body) is not None:
            raise OperationFailed(route_name, response, None, body)
        if self.status is None or not isinstance(body, dict):
            return self._finished(response, body)
        state = DottedPath(self.status).read(body)
        if state is None:
            return self._finished(response, body)
        if self._is(state, self.failed):
            raise OperationFailed(route_name, response, state, body)
        if state is True or self._is(state, self.succeeded):
            return self._finished(response, body)
        return PollStep("wait", self._status_url(response) or url, self._delay(response))

    def decode(self, response: httpx.Response) -> Any:
        """The result in a finished status body: the value at `result`, else the body."""
        body = _json(response)
        return body if self.result is None else DottedPath(self.result).read(body)

    def _finished(self, response: httpx.Response, body: Any) -> PollStep:
        if self.result_url is not None:
            url = DottedPath(self.result_url).read(body)
            if isinstance(url, str) and url:
                return PollStep("fetch", url)
        return PollStep("done", response=response)

    def _status_url(self, response: httpx.Response) -> str | None:
        for name in self.headers:
            value = response.headers.get(name)
            if value:
                return value
        return None

    def _names_operation(self, response: httpx.Response) -> bool:
        return any(
            name.lower() in ASYNC_HEADERS and name in response.headers for name in self.headers
        )

    def _delay(self, response: httpx.Response) -> float:
        try:
            retry_after = float(response.headers.get("retry-after", ""))
        except ValueError:
            return self.interval
        return max(self.interval, retry_after)

    @staticmethod
    def _is(state: Any, names: tuple[str, ...]) -> bool:
        return isinstance(state, str) and state.lower() in {name.lower() for name in names}


def _json(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return None
