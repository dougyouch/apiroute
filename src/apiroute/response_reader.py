from typing import Any

import httpx

from apiroute.unexpected_response import UnexpectedResponse


class ResponseReader:
    """Checks a response's status and turns it into what the route returns."""

    def __init__(self, route_name: str, expected: frozenset[int] | None, returns: str):
        self._route_name = route_name
        self._expected = expected
        self._returns = returns

    def read(self, response: httpx.Response) -> Any:
        self.check_status(response)
        return self._extract(response)

    def check_status(self, response: httpx.Response) -> None:
        if not self.is_expected(response.status_code):
            raise UnexpectedResponse(self._route_name, response)

    def is_expected(self, status_code: int) -> bool:
        if self._expected is None:
            return 200 <= status_code < 300
        return status_code in self._expected

    def _extract(self, response: httpx.Response) -> Any:
        if self._returns == "response":
            return response
        if self._returns == "bytes":
            return response.content
        if self._returns == "text":
            return response.text
        return response.json() if response.content else None
